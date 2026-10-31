"""診断専用。正解位置は判断や操作へ渡さない。表示変更の前後を監査する。"""
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
    import robosuite.macros as macros
    from robosuite.utils.mjcf_utils import IMAGE_CONVENTION_MAPPING
    sim=env._env.sim
    convention=IMAGE_CONVENTION_MAPPING[macros.IMAGE_CONVENTION]
    def camera_images():
        return {key:sim.render(camera_name=name,width=obs['pixels'][key].shape[1],height=obs['pixels'][key].shape[0],depth=False)[::convention].copy()
            for key,name in [('image','agentview'),('image2','robot0_eye_in_hand')]}
    def observable_fingerprint():
        records={}
        for name,o in env._env.env._observables.items():
            records[name]={k:hashlib.sha256(v.tobytes()).hexdigest() if isinstance(v,np.ndarray) else repr(v)
                for k,v in vars(o).items() if isinstance(v,(np.ndarray,bool,int,float,np.number))}
        return records
    observable_before=observable_fingerprint()
    visible_rerender=camera_images()
    visible_image_error={key:int(np.max(abs(visible_rerender[key].astype(int)-obs['pixels'][key].astype(int)))) for key in visible_rerender}
    assert not any(visible_image_error.values()),visible_image_error
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
    # robosuite 1.4.0 camera_rgbと同じrender/conventionを使い、Observable.updateは呼ばない。
    refreshed=dict(obs,pixels=camera_images())
    observable_after=observable_fingerprint()
    assert observable_before==observable_after
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
        'observable_numeric_state_unchanged':observable_before==observable_after,'pre_hide_render_matches_original_rgb_max_error':visible_image_error,'render_method':'direct sim.render with robosuite IMAGE_CONVENTION; no Observable update','policy_receives_refreshed_actual_cameras':True,'no_simulator_steps_or_state_reset_during_hide':True}
    assert any(audit['image_changed'].values())
    dump(folder/'leaf_display_audit.json',audit)
    return refreshed

def record_pose(obs,folder,label,step):
    import active_observation as ao
    dump(folder/(label+'.json'),dict(pose(obs),pre_action_frame_id=step,sim_elapsed_s=step/20))
    ao.save_views(obs,folder,label)
