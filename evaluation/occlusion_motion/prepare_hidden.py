"""診断コピーだけに、表示無効化・移動強制・姿勢記録を加える。"""
import ast
import difflib
import json
import shutil
from pathlib import Path

D = Path(__file__).resolve().parent
SOURCE = D/'workspace'
DEST = D/'hidden_workspace'
DEST.mkdir(exist_ok=False)
for folder in ['scripts','assets','tasks','evidence','experiments']:
    for src in (SOURCE/folder).rglob('*'):
        if not src.is_file() or '__pycache__' in src.parts:
            continue
        target=DEST/src.relative_to(SOURCE)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,target)

helper='''"""診断専用。正解位置は判断や操作へ渡さない。表示変更の前後を監査する。"""
import hashlib,json
import numpy as np
from pathlib import Path

def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

def arrays(obj,exclude=()):
    result={}
    for name in dir(obj):
        if name.startswith('_') or name in exclude:continue
        try:value=getattr(obj,name)
        except Exception:continue
        if isinstance(value,np.ndarray):
            result[name]=hashlib.sha256(value.tobytes()).hexdigest()
    return result

def rng_hashes():
    import random,pickle,torch
    return {'python':hashlib.sha256(pickle.dumps(random.getstate())).hexdigest(),
            'numpy':hashlib.sha256(pickle.dumps(np.random.get_state())).hexdigest(),
            'torch':hashlib.sha256(torch.get_rng_state().cpu().numpy().tobytes()).hexdigest(),
            'cuda':[hashlib.sha256(x.cpu().numpy().tobytes()).hexdigest() for x in torch.cuda.get_rng_state_all()]}

def pose(obs):
    return {'eef_position_world_m':np.asarray(obs['robot_state']['eef']['pos']).tolist(),
            'wrist_quaternion_xyzw':np.asarray(obs['robot_state']['eef']['quat']).tolist(),
            'gripper_qpos_m':np.asarray(obs['robot_state']['gripper']['qpos']).tolist()}

def hide_leaf(env,obs,folder):
    import active_observation as ao
    sim=env._env.sim
    ids=[i for i in range(sim.model.ngeom) if 'observation_leaf' in (sim.model.geom_id2name(i) or '')]
    assert len(ids)==2,ids
    records=[]
    for i in ids:
        assert sim.model.geom_contype[i]==0 and sim.model.geom_conaffinity[i]==0
        records.append({'id':i,'name':sim.model.geom_id2name(i),'rgba_before':sim.model.geom_rgba[i].tolist(),
            'group':int(sim.model.geom_group[i]),'contype':int(sim.model.geom_contype[i]),'conaffinity':int(sim.model.geom_conaffinity[i])})
    rng_before=rng_hashes()
    state_before=sim.get_state().flatten().copy()
    import mujoco
    sparse=bool(mujoco.mj_isSparse(sim.model._model))
    unused_dense_sparse_indices=[] if sparse else ['efc_AR_rowadr','efc_AR_rownnz']
    model_before=arrays(sim.model._model);data_before=arrays(sim.data._data,unused_dense_sparse_indices)
    ao.save_views(obs,folder,'visible_before_alpha_change')
    metrics_before=ao.image_metrics(obs);pose_before=pose(obs)
    for i in ids:sim.model.geom_rgba[i,3]=0
    # 使用中robosuite 1.4.0の既存API。env.step/set_stateは呼ばず、現在状態を再描画する。
    refreshed=env._format_raw_obs(env._env.env._get_observations(force_update=True))
    ao.save_views(refreshed,folder,'hidden_after_alpha_change')
    rng_after=rng_hashes()
    assert rng_before==rng_after
    state_after=sim.get_state().flatten().copy()
    model_after=arrays(sim.model._model);data_after=arrays(sim.data._data,unused_dense_sparse_indices)
    model_changed=[k for k in model_before if model_before[k]!=model_after[k]]
    data_changed=[k for k in data_before if data_before[k]!=data_after[k]]
    assert model_changed==['geom_rgba'],model_changed
    assert np.array_equal(state_before,state_after)
    assert not data_changed,data_changed
    for rec in records:rec['rgba_after']=sim.model.geom_rgba[rec['id']].tolist()
    for key in obs['pixels']:
        assert np.array_equal(obs['robot_state']['eef']['pos'],refreshed['robot_state']['eef']['pos'])
    audit={'mujoco_sparse_jacobian':sparse,'solver_id':int(sim.model.opt.solver),'nv':int(sim.model.nv),'inactive_sparse_workspace_excluded':unused_dense_sparse_indices,'model_numeric_arrays_changed':model_changed,'data_numeric_arrays_changed':data_changed,
        'simulator_state_unchanged':True,'rng_before':rng_before,'rng_after':rng_after,'all_four_rng_states_unchanged':True,'state_sha256_before':hashlib.sha256(state_before.tobytes()).hexdigest(),
        'state_sha256_after':hashlib.sha256(state_after.tobytes()).hexdigest(),'geom_records':records,
        'rgb_before':metrics_before,'rgb_after':ao.image_metrics(refreshed),'pose_before':pose_before,'pose_after':pose(refreshed),
        'image_changed':{k:not np.array_equal(obs['pixels'][k],refreshed['pixels'][k]) for k in obs['pixels']},
        'policy_receives_refreshed_actual_cameras':True,'no_simulator_steps_or_state_reset_during_hide':True}
    assert any(audit['image_changed'].values())
    dump(folder/'leaf_display_audit.json',audit)
    return refreshed

def record_pose(obs,folder,label,step):
    import active_observation as ao
    dump(folder/(label+'.json'),dict(pose(obs),pre_action_frame_id=step,sim_elapsed_s=step/20))
    ao.save_views(obs,folder,label)
'''
(DEST/'scripts/diagnostic_hooks.py').write_text(helper,encoding='utf-8')
path=DEST/'scripts/run_rollout.py';original=path.read_text(encoding='utf-8');text=original
def replace(old,new):
    global text
    assert text.count(old)==1,old
    text=text.replace(old,new)
replace('    for episode,setup in enumerate(setups):\n',
'''    for episode,setup in enumerate(setups):
        if setup.get('diagnostic_latest_start_unix') and time.time()>setup['diagnostic_latest_start_unix']:
            dump(out/'diagnostic_deadline_stop.json',{'next_episode_not_started':episode,'reason':'60min trial-start budget'})
            break
''')
replace("        if args.fruit_task:obs=occlusion_scene.apply_setup(env,obs,setup,args.initial_state,args.setup_tray_xy)\n", 
'''        if args.fruit_task:
            obs=occlusion_scene.apply_setup(env,obs,setup,args.initial_state,args.setup_tray_xy)
            import diagnostic_hooks as dh
            if setup.get('diagnostic_hide_leaf'):
                obs=dh.hide_leaf(env,obs,epdir/'diagnostic')
            dh.record_pose(obs,epdir/'diagnostic','initial_pose',0)
''')
replace("        decision=ao.decide(obs) if args.fruit_task else None\n",
'''        decision=ao.decide(obs) if args.fruit_task else None
        if decision is not None:
            decision['diagnostic_raw_rgb_trigger']=decision['trigger']
            decision['diagnostic_force_observation']=bool(setup.get('diagnostic_force_observation'))
            if setup.get('diagnostic_force_observation'):
                assert active_enabled and args.observer_profile=='rgb_early_approach_v10'
                decision['trigger']=True
                decision['reason']='DIAGNOSTIC forced fixed v10 motion despite actual RGB trigger'
''')
replace("        for step in range(args.max_steps):\n", "        diagnostic_operation_start_saved=False\n        for step in range(args.max_steps):\n")
replace("            policy_observation = dict(obs,robot_state=batched_state(obs['robot_state']))\n",
'''            if args.fruit_task:
                if step==45:dh.record_pose(obs,epdir/'diagnostic','matched45_pose',step)
                if not is_observation and not diagnostic_operation_start_saved:
                    diagnostic_operation_start_saved=True
                    dh.record_pose(obs,epdir/'diagnostic','operation_start',step)
            policy_observation = dict(obs,robot_state=batched_state(obs['robot_state']))
''')
ast.parse(text);ast.parse(helper)
path.write_text(text,encoding='utf-8')
(D/'diagnostic_source.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='採用コピー/run_rollout.py',tofile='診断コピー/run_rollout.py')),encoding='utf-8')
plan=json.loads((D/'PLAN.json').read_text(encoding='utf-8'))
by={(x['case_id'],x['active_reobservation']):x for x in plan['fixed_original_setups']}
order=[('new_leaf_00',False),('new_leaf_00',True),('new_leaf_04',True),('new_leaf_04',False),('new_leaf_07',False),('new_leaf_07',True)]
import datetime
deadline=datetime.datetime.fromisoformat(plan['new_trial_start_deadline_utc']).timestamp()
cases=[]
for name,move in order:
    case=dict(by[name,move],diagnostic_hide_leaf=True,diagnostic_force_observation=move,
              diagnostic_latest_start_unix=deadline,diagnostic_condition='葉表示なし・'+('45step移動強制' if move else '移動なし'))
    cases.append(case)
(DEST/'hidden_setups.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
plan['precommitted_hidden_execution_order']=[dict(case_id=n,force_motion=m) for n,m in order]
(D/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print('診断コピーと固定6条件を準備。まだ診断6試行は開始していない。')
