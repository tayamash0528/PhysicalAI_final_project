"""GT-position diagnostic servo, explicitly excluded from VLA evaluation."""
import argparse,json,random,time,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import imageio.v2 as iio
import run_rollout as rr
import fruit_objects
from arm_telemetry import ArmTelemetry
from placement_score import contained,gripper_released,PlacementHold
from lerobot.processor.env_processor import LiberoProcessorStep

p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=1000)
p.add_argument('--out',required=True);p.add_argument('--initial-state',default=None)
p.add_argument('--place',action='store_true');p.add_argument('--save-dataset',action='store_true')
p.add_argument('--tray-xy',type=float,nargs=2,default=None,help='Initial scene setup only; never a policy input')
p.add_argument('--compact',action='store_true',help='Remove non-observable long stationary dwell before stage changes')
p.add_argument('--apple-xy',type=float,nargs=2,default=None,help='Initial scene setup only')
p.add_argument('--wrist-reference-json',default=None,help='Proprioceptive reference orientation and local pad offset for a post-observation teacher')
a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
random.seed(a.seed);np.random.seed(a.seed)
task=SimpleNamespace(name='apple_single',language='diagnostic grasp only',problem_folder='',
    bddl_file=str(Path('tasks/apple_single.bddl').resolve()))
class Suite:
    def get_task(self,_):return task
env=rr.LiberoEnv(Suite(),0,'libero_spatial',observation_height=256,observation_width=256,
    obs_type='pixels_agent_pos',control_freq=20,init_states=False,hard_reset=True,episode_length=1000)
obs,_=env.reset(seed=a.seed)
if a.initial_state:
    raw=env._env.set_init_state(np.load(a.initial_state));obs=env._format_raw_obs(raw)
if a.tray_xy:
    item=env._env.env.objects_dict['tray_1'];q=env._env.sim.data.get_joint_qpos(item.joints[0]).copy()
    q[:2]=a.tray_xy;env._env.sim.data.set_joint_qpos(item.joints[0],q);env._env.sim.forward()
    for _ in range(10):raw,_,_,_=env._env.step([0,0,0,0,0,0,-1])
    obs=env._format_raw_obs(raw)
if a.apple_xy:
    item=env._env.env.objects_dict['apple_1'];q=env._env.sim.data.get_joint_qpos(item.joints[0]).copy()
    q[:2]=a.apple_xy;env._env.sim.data.set_joint_qpos(item.joints[0],q);env._env.sim.forward()
    for _ in range(10):raw,_,_,_=env._env.step([0,0,0,0,0,0,-1])
    obs=env._format_raw_obs(raw)
tele=ArmTelemetry(env);sim=env._env.sim
initial_state=sim.get_state().flatten();np.save(out/'initial_sim_state.npy',initial_state)
initial=tele.initial_pos.copy()
padmid=(np.mean(sim.data.geom_xpos[tele.left_pad],axis=0)+np.mean(sim.data.geom_xpos[tele.right_pad],axis=0))/2
offset=padmid-np.asarray(obs['robot_state']['eef']['pos'])
wrist_reference=json.loads(Path(a.wrist_reference_json).read_text()) if a.wrist_reference_json else None
if wrist_reference:
    from scipy.spatial.transform import Rotation
    reference_mat=np.asarray(wrist_reference['eef_rotation_matrix'])
    offset=reference_mat@np.asarray(wrist_reference['padmid_offset_eef_local_m'])
grasp=initial-offset
manifest={'mode':'diagnostic_GT_servo_NOT_VLA','gt_used':True,'success_included_in_vla_metrics':False,
    'place_requested':a.place,'dataset_saved':a.save_dataset,
    'initial_setup_tray_xy_m':a.tray_xy,
    'initial_setup_apple_xy_m':a.apple_xy,
    'compact_observation_driven_teacher':a.compact,'wrist_reference_json':a.wrist_reference_json,
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'seed':a.seed,'initial_state_sha256':hashlib.sha256(initial_state.tobytes()).hexdigest(),
    'pre_registered_criterion':{'lift_relative_initial_m':.05,'continuous_bilateral_hold_seconds':2.0},
    'requested_lift_m':.10,'control_hz':20,'position_servo_gain':.5,'max_commanded_translation_m':.01,
    'initial_padmid_minus_eef_m':offset.tolist(),'grasp_eef_target_m':grasp.tolist(),
    'telemetry':tele.metadata(),'no_teleport_fixed_constraints_or_disabled_contacts':True}
rr.dump(out/'manifest.json',manifest)
writer=iio.get_writer(str(out/'diagnostic_grasp.mp4'),fps=20,codec='libx264',quality=8)
log=(out/'telemetry.jsonl').open('w');step=0;summary=[];t0=time.perf_counter()
dataset={'image':[],'image2':[],'state':[],'action':[]};env_processor=LiberoProcessorStep()
placement=PlacementHold();tray=env._env.env.objects_dict['tray_1'];tray_id=sim.model.body_name2id(tray.root_body)
vertices=np.array([[float(x) for x in line.split()[1:]] for line in Path('assets/apple/apple.obj').read_text().splitlines() if line.startswith('v ')])
phases=[('approach',grasp+np.array([0,0,.15]),-1,100),
        ('descend',grasp,-1,100),('close',grasp,1,50),
        ('lift',grasp+np.array([0,0,.10]),1,100),('hold',grasp+np.array([0,0,.10]),1,60)]
if a.place:
    target_center=sim.data.body_xpos[tray_id].copy()+np.array([0,0,.004+.034])
    place_eef=target_center-offset
    phases += [('transport',place_eef+np.array([0,0,.12]),1,140),
               ('lower_to_tray',place_eef,1,120),('release',place_eef,-1,70),
               ('retreat',place_eef+np.array([0,0,.15]),-1,100),
               ('verify_placement',place_eef+np.array([0,0,.15]),-1,50)]
if a.compact:
    phases=[(name,target,grip,(20 if name=='close' else 30 if name=='release' else limit))
            for name,target,grip,limit in phases if name!='hold']
try:
    for phase,target,grip,limit in phases:
        last=None
        for j in range(limit):
            current=np.asarray(obs['robot_state']['eef']['pos'])
            desired_delta=np.clip(.5*(target-current),-.01,.01)
            rot_command=np.zeros(3);ori_error=0.
            if wrist_reference:
                current_mat=Rotation.from_quat(obs['robot_state']['eef']['quat']).as_matrix()
                err=Rotation.from_matrix(reference_mat@current_mat.T).as_rotvec();ori_error=float(np.linalg.norm(err))
                rot_command=np.clip(.5*err,-.03,.03)/.5
            action=np.r_[desired_delta/.05,rot_command,grip]
            if a.save_dataset:
                observed=env_processor.observation(rr.preprocess_observation(dict(obs,robot_state=rr.batched_state(obs['robot_state']))))
                for key in ['image','image2']:
                    dataset[key].append(observed[f'observation.images.{key}'][0].mul(255).byte().permute(1,2,0).numpy())
                dataset['state'].append(observed['observation.state'][0].numpy())
                dataset['action'].append(action.astype(np.float32))
            obs,_,_,_,_=env.step(action)
            last=tele.sample(step,action,obs,phase)
            inside=contained(sim.data.body_xpos[tele.body],sim.data.body_xmat[tele.body].reshape(3,3),
                vertices,sim.data.body_xpos[tray_id],sim.data.body_xmat[tray_id].reshape(3,3))
            placed=placement.update(inside,gripper_released(obs['robot_state']['gripper']['qpos'],action[-1]))
            last.update({'action':action.tolist(),'inside_tray':inside,'placement_hold_steps':placement.streak,
                         'project_placement_success':placed,'placement_evaluator_version':'v2_open_command_75mm_40steps'})
            log.write(json.dumps(last)+'\n');writer.append_data(rr.panel(obs,f'DIAGNOSTIC GT SERVO / {phase} / step={step}'))
            step+=1
            if a.compact:
                error=float(np.linalg.norm(target-np.asarray(obs['robot_state']['eef']['pos'])))
                if phase in ['descend','lower_to_tray'] and j>=15 and error<.008 and ori_error<.03:break
                if phase=='close' and j>=5 and last['stages']['bilateral_contact']:break
                if phase=='release' and j>=5 and gripper_released(obs['robot_state']['gripper']['qpos'],action[-1]):break
            if phase in ['approach','descend','lift','transport','lower_to_tray','retreat'] and j>=15 and np.linalg.norm(target-np.asarray(obs['robot_state']['eef']['pos']))<.003 and ori_error<.03:break
        summary.append({'phase':phase,'steps':j+1,'target_eef_m':target.tolist(),
                        'last_eef_error_m':float(np.linalg.norm(target-np.asarray(obs['robot_state']['eef']['pos']))),
                        'last_measurement':last})
        print(phase,'steps',j+1,'lift',last['object_lift_from_initial_m'],'bilateral',last['stages']['bilateral_contact'],flush=True)
finally:
    writer.close();log.close();env.close()
result={'mode':manifest['mode'],'vla_result':False,'diagnostic_success':tele.stage_counts.get('lift_50mm_hold_2s_bilateral',0)>0,
    'teacher_placement_success':placement.success,'placement_evaluator_version':'v2_open_command_75mm_40steps',
    'phases':summary,'stage_counts':tele.stage_counts,'steps':step,'sim_seconds':step/20,
    'wall_seconds':time.perf_counter()-t0}
rr.dump(out/'result.json',result);print(json.dumps(result['stage_counts']),flush=True)
if a.save_dataset:
    arrays={key:np.asarray(value) for key,value in dataset.items()}
    np.savez_compressed(out/'teacher_episode.npz',**arrays)
    rr.dump(out/'dataset_manifest.json',{'format':'project_npz_v1','split':'train','seed':a.seed,
        'fps':20,'frames':step,'features':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in arrays.items()},
        'task':'pick up the apple and place it in the tray','image_transform':'official LiberoProcessorStep 180-degree rotation',
        'state':'eef XYZ + axisangle XYZ + opposed gripper qpos (8D), no object pose',
        'action':'OSC relative XYZ/rot/gripper (7D), physical control bounds [-1,1]',
        'demonstrator':'GT-position servo, not a VLA','gt_fields_in_policy_features':False,
        'valid_successful_placement':placement.success,'held_out_evaluation_seeds':[1001,1002]})
    print('DATASET',out/'teacher_episode.npz','frames',step,'placement',placement.success,flush=True)
