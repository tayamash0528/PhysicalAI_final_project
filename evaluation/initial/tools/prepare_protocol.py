"""Freeze a20-trial protocol after development and before any main outcomes."""
import sys,argparse,datetime,hashlib,json,random,shutil
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path('scripts').resolve()))
import numpy as np
import run_rollout as rr
import fruit_objects,occlusion_scene as scene,active_observation as ao
BASE=Path('evaluation/initial')
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--selection',required=True);p.add_argument('--reserved',default=str(BASE/'reserved_evaluation_v2.json'));a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
selected=json.loads(Path(a.selection).read_text());reserved=json.loads(Path(a.reserved).read_text());assert selected['observer_profile']=='rgb_early_approach_v10'
sources=[Path('scripts')/n for n in ['run_rollout.py','active_observation.py','occlusion_scene.py','arm_telemetry.py','placement_score.py','fruit_objects.py']]
(out/'locked_sources').mkdir()
for s in sources:shutil.copy2(s,out/'locked_sources'/s.name)
shutil.copy2(__file__,out/Path(__file__).name)
teacher_dirs=[Path('training/initial_demonstration')]+list(Path('training/demonstrations').glob('train_*'))+list(Path('improvements/20261030_2101/teachers_06').glob('teacher_*'))+list(Path('improvements/20261031_0349/normal_wrist_teachers_04').glob('teacher_*'))
teacher_dirs=[d for d in teacher_dirs if d.is_dir() and (d/'manifest.json').is_file()]
teacher_xy=[json.loads((d/'manifest.json').read_text())['telemetry']['initial_object_root_world_m'][:2] for d in teacher_dirs]
devxy=json.loads((BASE/'DEVELOPMENT_PLAN.json').read_text())['development_xy'];audit=[]
for xy in reserved['layout_xy_m']:
    dt=min(float(np.linalg.norm(np.asarray(xy)-t)) for t in teacher_xy);dd=min(float(np.linalg.norm(np.asarray(xy)-d)) for d in devxy)
    assert dt>.004 and dd>.004;audit.append({'xy':xy,'nearest_local_teacher_distance_m':dt,'nearest_this_round_development_distance_m':dd})
rr.dump(out/'split_audit.json',{'role':'setup/evaluation_only','checks':audit,'development_inputs_were_not_reserved_layouts':True,'pretraining_data_overlap_unknown':True})
task=SimpleNamespace(name='apple_single',language='pick up the apple and place it in the tray',problem_folder='',bddl_file=str(Path('tasks/apple_single.bddl').resolve()))
class Suite:
    def get_task(self,_):return task
truth=[];cases=[];rng=random.Random(17001)
for j in range(10):
    i=j%5;kind='none' if j<5 else 'leaf_visual';case=f'{"clear" if j<5 else "leaf"}_{i:02d}';seed=8400+j;xy=reserved['layout_xy_m'][i];scene.install(kind,selected['half_size_m'] if kind=='leaf_visual' else None)
    env=rr.LiberoEnv(Suite(),0,'libero_spatial',observation_height=256,observation_width=256,obs_type='pixels_agent_pos',control_freq=20,init_states=False,hard_reset=True,episode_length=900)
    obs,_=env.reset(seed=seed)
    setup={'initial_state':'training/demonstrations/train_00/initial_sim_state.npy','apple_xy':xy,'tray_xy':[.04,.15],'occlusion':kind,
        'leaf_height_above_root_m':selected['height_above_root_m'],'leaf_anchor':'initial_wrist_ray','leaf_half_size_m':selected['half_size_m']}
    obs=scene.apply_setup(env,obs,setup);d=out/'initial_states'/case;d.mkdir(parents=True);state=env._env.sim.get_state().flatten();np.save(d/'state.npy',state);ao.save_views(obs,d,'initial')
    truth.append({'case_id':case,'seed':seed,'occlusion':kind,'setup_evaluation_only':setup,'state_file_sha256':sha(d/'state.npy'),'state_array_sha256':hashlib.sha256(state.tobytes()).hexdigest(),'initial_rgb_trigger':ao.decide(obs),'object_positions_evaluation_only':rr.evaluator(env)})
    pair=[]
    for active in [False,True]:pair.append({'case_id':case,'initial_state':str(d/'state.npy'),'scene_prepared':True,'occlusion':kind,'leaf_half_size_m':selected['half_size_m'] if kind=='leaf_visual' else None,
        'seed':seed,'active_reobservation':active,'split':'reserved_positions_never_executed_before_main'})
    rng.shuffle(pair);cases.append(pair);env.close();print('prepared',case,flush=True)
rng.shuffle(cases);setups=[x for pair in cases for x in pair];rr.dump(out/'episode_setups.json',setups);rr.dump(out/'evaluation_only_conditions.json',truth)
delta='models/fruit_vla/expert_delta.safetensors'
assets=[Path(x) for x in ['tasks/apple_single.bddl','assets/apple/apple.xml','assets/apple/apple.obj','assets/tray/tray.xml']]
lock={'status':'LOCKED_BEFORE_MAIN_TRIALS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'trials':20,'cases':10,'clear_cases':5,'leaf_cases':5,
    'delta':delta,'delta_sha256':sha(delta),'base_model':json.loads(Path('evidence/model.json').read_text()),'source_sha256':{str(s):sha(s) for s in sources},'asset_sha256':{str(s):sha(s) for s in assets},
    'episode_setups_sha256':sha(out/'episode_setups.json'),'reserved_layouts_file':a.reserved,'reserved_layouts_sha256':sha(a.reserved),'max_steps':900,'max_sim_seconds':45,'control_freq_hz':20,'n_action_steps':10,
    'instruction':task.language,'placement_evaluator':'v2_open_command_and_75mm_gap_40_steps','grasp_definition':'50mm above initial fruit center with bilateral contact continuously40steps=2seconds; contact alone separate',
    'observer_profile':selected['observer_profile'],'observer_rule':ao.EARLY_APPROACH_RULE,'trigger_rule':ao.TRIGGER_RULE,'matched_visibility_eval_step':45,
    'leaf_geometry':selected,'leaf_contacts_enabled':False,'support_omitted':True,'fixed_camera_sees_apple':True,'operation_images_updated_in_both_methods':True,
    'observation_in_shared_total_time':True,'initial_states':truth,'order_seed':17001,'selection_evidence':a.selection,'selection_evidence_sha256':sha(a.selection),
    'no_results_seen_before_lock':True,'no_tuning_after_main':True,'counts_and_positions_not_policy_inputs':True}
rr.dump(out/'LOCK.json',lock);print('LOCKED',flush=True)
