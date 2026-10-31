"""Scene setup only: a free, colliding 2g rigid leaf. No policy decisions here."""
import xml.etree.ElementTree as ET
import numpy as np
from robosuite.models.tasks.manipulation_task import ManipulationTask
ORIGINAL=ManipulationTask.__init__
LEAF={'half_size_m':[.05,.035,.001],'mass_kg':.002,'friction':[.3,.003,.0003],
      'joint':'free','contact_enabled':True,'rgba':[.12,.55,.08,1]}
def configuration(kind):
    if kind=='none':return None
    return dict(LEAF,contact_enabled=kind=='leaf',gravity_compensation=1 if kind=='leaf_visual' else 0,
        visual_only_simplification=kind=='leaf_visual')
def install(kind,half_size_m=None):
    if kind=='none':ManipulationTask.__init__=ORIGINAL;return
    if kind not in ('leaf','leaf_visual'):raise ValueError(kind)
    if half_size_m is not None and kind!='leaf_visual':raise ValueError('Geometry override is for the visual-only research leaf')
    size=np.asarray(half_size_m if half_size_m is not None else LEAF['half_size_m'],dtype=float)
    if size.shape!=(3,) or not np.all((size>0)&(size<=.10)):raise ValueError('Invalid leaf dimensions')
    size_text=' '.join(str(float(x)) for x in size)
    def init(self,*args,**kwargs):
        ORIGINAL(self,*args,**kwargs)
        # Visual-only diagnostic: gravity-compensated free body, zero contacts.
        # It stays at its setup pose; neither robot nor fruit is fixed or modified.
        b=ET.SubElement(self.worldbody,'body',name='observation_leaf',pos='0 0 1.4',
            **({'gravcomp':'1'} if kind=='leaf_visual' else {}))
        ET.SubElement(b,'freejoint',name='observation_leaf_joint')
        ET.SubElement(b,'geom',name='observation_leaf_collision',type='box',size=size_text,
          mass='.002',friction='.3 .003 .0003',rgba='.12 .55 .08 1',
          contype='0' if kind=='leaf_visual' else '1',conaffinity='0' if kind=='leaf_visual' else '1',group='0')
        # robosuite 1.4 renders group 1 while keeping the real group-0 contacts.
        ET.SubElement(b,'geom',name='observation_leaf_visual',type='box',size=size_text,
          mass='0',rgba='.12 .55 .08 1',contype='0',conaffinity='0',group='1')
    ManipulationTask.__init__=init
def restore(env,flat,kind):
    sim=env._env.sim;flat=np.asarray(flat)
    if len(flat)!=len(sim.get_state().flatten()):
        assert kind in ('leaf','leaf_visual')
        nq=sim.model.nq-7;nv=sim.model.nv-6
        assert len(flat)==1+nq+nv
        leaf=sim.data.get_joint_qpos('observation_leaf_joint').copy()
        flat=np.concatenate([flat[:1+nq],leaf,flat[1+nq:],np.zeros(6)])
    return env._env.set_init_state(flat)
def place_leaf_at_initial_scene(env,offset=(0,0),height_above_root_m=.038,anchor='apple'):
    # Evaluation/setup truth is used only before a rollout begins.
    sim=env._env.sim;obj=env._env.env.objects_dict['apple_1']
    p=sim.data.body_xpos[sim.model.body_name2id(obj.root_body)].copy()
    if anchor=='initial_wrist_ray':
        # Scene setup ONLY: place a raised occluder on the initial wrist/fruit ray.
        # The body remains visual-only when leaf_visual is installed. No truth
        # leaves this setup function or enters the observer/policy.
        cid=sim.model.camera_name2id('robot0_eye_in_hand');camera=sim.data.cam_xpos[cid].copy()
        alpha=height_above_root_m/(camera[2]-p[2])
        if not 0<alpha<1:raise ValueError('Leaf must be between fruit and initial camera')
        p[:2]+=alpha*(camera[:2]-p[:2])
    elif anchor!='apple':raise ValueError(anchor)
    p[:2]+=np.asarray(offset);p[2]+=height_above_root_m
    sim.data.set_joint_qpos('observation_leaf_joint',np.r_[p,[1,0,0,0]])
    sim.data.set_joint_qvel('observation_leaf_joint',np.zeros(6));sim.forward()
def apply_setup(env,obs,setup,initial_state=None,tray_xy=None):
    kind=setup.get('occlusion','none');initial_state=setup.get('initial_state',initial_state)
    if initial_state:
        raw=restore(env,np.load(initial_state),kind);obs=env._format_raw_obs(raw)
    if setup.get('scene_prepared'):return obs
    tray_xy=setup.get('tray_xy',tray_xy);apple_xy=setup.get('apple_xy')
    if tray_xy is not None or apple_xy is not None:
        sim=env._env.sim
        for name,xy in [('tray_1',tray_xy),('apple_1',apple_xy)]:
            if xy is None:continue
            item=env._env.env.objects_dict[name];q=sim.data.get_joint_qpos(item.joints[0]).copy();q[:2]=xy
            sim.data.set_joint_qpos(item.joints[0],q)
        sim.forward()
        for _ in range(10):raw,_,_,_=env._env.step([0,0,0,0,0,0,-1])
        obs=env._format_raw_obs(raw)
    if kind in ('leaf','leaf_visual'):
        place_leaf_at_initial_scene(env,setup.get('leaf_offset_xy',[0,0]),setup.get('leaf_height_above_root_m',.038),setup.get('leaf_anchor','apple'))
        for _ in range(10):raw,_,_,_=env._env.step([0,0,0,0,0,0,-1])
        obs=env._format_raw_obs(raw)
    return obs
