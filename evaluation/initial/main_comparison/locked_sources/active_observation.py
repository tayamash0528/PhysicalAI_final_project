"""RGB-only uncertainty proxy and fixed observation motion; no object truth inputs."""
import numpy as np
from PIL import Image
RULE={'version':'rgb_green_occluder_red_evidence_v3','min_green_pixels':250,'min_red_share':.75,
      'max_additional_views':1,'motion_steps':60,'relative_eef_x_m':0,'relative_eef_z_m':-.08,
      'edge_centroid_threshold_px':225,'near_centroid_y_shift_m':-.02,'edge_centroid_y_shift_m':.06,
      'scope':'red apple and green rigid leaf in this synthetic scene; not a general detector'}
TRIGGER_RULE={k:RULE[k] for k in ['min_green_pixels','min_red_share','scope']}
TRIGGER_RULE['version']='rgb_green_red_trigger_v1'
def image_metrics(obs):
    result={};red=green=0
    for key,img in obs['pixels'].items():
        a=img[::-1,::-1].astype(np.float32);r,g,b=a[...,0],a[...,1],a[...,2]
        mr=(r>80)&(r>1.5*g)&(r>1.5*b);mg=(g>60)&(g>1.4*r)&(g>1.3*b)
        nr=int(mr.sum());ng=int(mg.sum())
        result[key]={'red_pixels':nr,'green_pixels':ng,'green_centroid_x_px':float(np.where(mg)[1].mean()) if ng else None,
            'red_centroid_y_px':float(np.where(mr)[0].mean()) if nr else None};red+=nr;green+=ng
    return {'views':result,'red_pixels':red,'green_pixels':green,'red_share':red/max(red+green,1)}
def decide(obs):
    m=image_metrics(obs)
    trigger=m['green_pixels']>=RULE['min_green_pixels'] and m['red_share']<RULE['min_red_share']
    return {'trigger':bool(trigger),'metrics':m,'reason':'green occluder with weak red evidence' if trigger else 'sufficient red evidence or no green occluder',
            'inputs':['actual image RGB','actual image2 RGB'],'uses_object_truth':False}
def observation_target(obs):
    cx=image_metrics(obs)['views']['image2']['green_centroid_x_px']
    edge=cx is None or cx>RULE['edge_centroid_threshold_px']
    dy=RULE['edge_centroid_y_shift_m'] if edge else RULE['near_centroid_y_shift_m']
    return np.asarray(obs['robot_state']['eef']['pos'])+np.array([RULE['relative_eef_x_m'],dy,RULE['relative_eef_z_m']])
def action(obs,target):
    error=target-np.asarray(obs['robot_state']['eef']['pos'])
    xyz=np.clip(.5*error,-.006,.006)/.05
    return np.r_[xyz,np.zeros(3),-1.]
def save_views(obs,folder,label):
    folder.mkdir(exist_ok=True,parents=True)
    for key,img in obs['pixels'].items():Image.fromarray(img[::-1,::-1]).save(folder/f'{label}_{key}.png')

CANDIDATE_RULE={'version':'rgb_candidate_views_v5_live_quaternion','steps_per_move':90,'max_moves':3,
    'early_stop_red_pixels':150,'early_stop_red_share':.15,
    'candidate_offsets_m':[[0,-.08,-.16],[.13,.08,-.16]],
    'candidate_world_rotvec_rad':[[.75,0,0],[.65,.50,0]],
    'selection':'actual wrist RGB red_share * min(red_pixels/150,1); no truth/reference render',
    'scope':'scene-specific red apple / green occluder color evidence, not general recognition'}

class CandidateObserver:
    """At most two RGB-scored views and one return to the better actual pose."""
    def __init__(self,obs):
        from scipy.spatial.transform import Rotation
        self.Rotation=Rotation;self.origin=np.asarray(obs['robot_state']['eef']['pos']).copy()
        self.origin_mat=Rotation.from_quat(obs['robot_state']['eef']['quat']).as_matrix()
        self.targets=[(self.origin+xyz,Rotation.from_rotvec(rot).as_matrix()@self.origin_mat)
            for xyz,rot in zip(CANDIDATE_RULE['candidate_offsets_m'],CANDIDATE_RULE['candidate_world_rotvec_rad'])]
        self.target_index=0;self.move_steps=0;self.done=False;self.visits=[];self.returning=False
    @property
    def target(self):return self.targets[self.target_index]
    def action(self,obs):
        target,mat=self.target
        current=self.Rotation.from_quat(obs['robot_state']['eef']['quat']).as_matrix()
        error=self.Rotation.from_matrix(mat@current.T).as_rotvec()
        return np.r_[np.clip(.5*(target-np.asarray(obs['robot_state']['eef']['pos'])),-.006,.006)/.05,
            np.clip(.5*error,-.03,.03)/.5,-1.]
    def update(self,obs):
        self.move_steps+=1
        if self.move_steps<CANDIDATE_RULE['steps_per_move']:return False
        metrics=image_metrics(obs);m=metrics['views']['image2'];nr=m['red_pixels'];ng=m['green_pixels'];share=nr/max(nr+ng,1)
        score=share*min(nr/150,1)
        self.visits.append({'candidate_index':self.target_index,'return_to_best':self.returning,
            'rgb_metrics':metrics,'score':score,'actual_eef_m':np.asarray(obs['robot_state']['eef']['pos']).tolist(),
            'target_eef_m':self.target[0].tolist()})
        self.move_steps=0
        if self.returning or (nr>=150 and share>=.15):self.done=True
        elif self.target_index==0:self.target_index=1
        elif self.visits[0]['score']>score:self.target_index=0;self.returning=True
        else:self.done=True
        return True

ALIGNED_RULE=dict(CANDIDATE_RULE,version='rgb_candidate_views_v6_pixel_alignment',
    max_moves=6,candidate_max_moves=3,
    alignment_target_red_centroid_y_px=104.,alignment_tolerance_px=8.,
    alignment_x_increment_m=.01,alignment_steps_per_move=20,alignment_max_moves=3,
    alignment_calibration='Rounded midpoint of two successful teacher-start wrist RGB red centroids (103.009,105.373). No object positions/counts.',
    alignment_scope='Observation-only horizontal x move, open gripper; hold actual post-view height/orientation. No grasp targets.',
    max_total_observation_steps=330)

MINIMAL_TILT_RULE=dict(CANDIDATE_RULE,version='rgb_minimal_tilt_v7',
    candidate_offsets_m=[[0,-.08,-.16],[0,-.08,-.16]],
    candidate_world_rotvec_rad=[[.30,0,0],[.60,0,0]],
    early_stop_red_pixels=200,early_stop_red_share=.07,
    selection='Smallest rotation with >=200 actual wrist red pixels and >=0.07 red share; otherwise choose RGB-scored better view.',
    reason='One-factor rotation candidate change after fixed-translation diagnostic; same scene, cameras and proprioception.')

class MinimalTiltObserver(CandidateObserver):
    """Same translation as v5, smaller RGB-selected wrist rotations."""
    def __init__(self,obs):
        super().__init__(obs)
        self.targets=[(self.origin+xyz,self.Rotation.from_rotvec(rot).as_matrix()@self.origin_mat)
            for xyz,rot in zip(MINIMAL_TILT_RULE['candidate_offsets_m'],MINIMAL_TILT_RULE['candidate_world_rotvec_rad'])]
    def update(self,obs):
        self.move_steps+=1
        if self.move_steps<MINIMAL_TILT_RULE['steps_per_move']:return False
        metrics=image_metrics(obs);m=metrics['views']['image2'];nr=m['red_pixels'];share=nr/max(nr+m['green_pixels'],1)
        score=share*min(nr/200,1)
        self.visits.append({'candidate_index':self.target_index,'return_to_best':self.returning,
            'rgb_metrics':metrics,'score':score,'actual_eef_m':np.asarray(obs['robot_state']['eef']['pos']).tolist(),
            'target_eef_m':self.target[0].tolist()})
        self.move_steps=0
        if self.returning or (nr>=200 and share>=.07):self.done=True
        elif self.target_index==0:self.target_index=1
        elif self.visits[0]['score']>score:self.target_index=0;self.returning=True
        else:self.done=True
        return True

NORMAL_WRIST_RULE={'version':'rgb_normal_wrist_v8','steps_per_move':90,'max_moves':1,
    'candidate_offsets_m':[[.10,.12,-.08]],'candidate_world_rotvec_rad':[[0,0,0]],
    'scope':'One open-gripper observation above the declared workspace; initial wrist orientation retained. Raised visual-leaf experiment only.',
    'success_proxy_min_red_pixels':200,'uses_object_truth':False,
    'selection':'RGB trigger; single preregistered actual wrist view. Visibility checked separately, not a placement success.'}

class NormalWristObserver(CandidateObserver):
    """Observation only, keeps vertical grasp orientation and real camera identity."""
    def __init__(self,obs):
        super().__init__(obs)
        self.targets=[(self.origin+np.array([.10,.12,-.08]),self.origin_mat.copy())]
    def update(self,obs):
        self.move_steps+=1
        if self.move_steps<NORMAL_WRIST_RULE['steps_per_move']:return False
        metrics=image_metrics(obs);m=metrics['views']['image2']
        self.visits.append({'candidate_index':0,'rgb_metrics':metrics,'actual_eef_m':np.asarray(obs['robot_state']['eef']['pos']).tolist(),
            'target_eef_m':self.target[0].tolist(),'red_evidence_sufficient':m['red_pixels']>=200,'uses_object_truth':False})
        self.done=True
        return True

NORMAL_WRIST_PREGRASP_RULE=dict(NORMAL_WRIST_RULE,version='rgb_normal_wrist_v9_pregrasp',
    candidate_offsets_m=[[.06,.12,-.08]],
    reason='Only x observation offset changed from v8. Avoid overshooting fruit x-range; v8 teacher required initial negative x while base mostly approaches positive x. Also reduces wrist vertical pixel displacement.')

class NormalWristPregraspObserver(NormalWristObserver):
    def __init__(self,obs):
        super().__init__(obs)
        self.targets=[(self.origin+np.array([.06,.12,-.08]),self.origin_mat.copy())]

EARLY_APPROACH_RULE={'version':'rgb_early_approach_v10','steps_per_move':45,'max_moves':1,
    'candidate_offsets_m':[[.020,.040,-.010]],'candidate_world_rotvec_rad':[[0,0,0]],
    'selection':'Initial RGB-only occlusion trigger; fixed small early-approach observation, no object pose/count.',
    'scope':'Small elevated visual leaf on initial wrist ray; open gripper, preserve initial wrist orientation.',
    'uses_object_truth':False,'success_proxy_min_red_pixels':200}

class EarlyApproachObserver(NormalWristObserver):
    def __init__(self,obs):
        super().__init__(obs)
        self.targets=[(self.origin+np.array([.020,.040,-.010]),self.origin_mat.copy())]
    def update(self,obs):
        self.move_steps+=1
        if self.move_steps<EARLY_APPROACH_RULE['steps_per_move']:return False
        metrics=image_metrics(obs);m=metrics['views']['image2']
        self.visits.append({'candidate_index':0,'rgb_metrics':metrics,'actual_eef_m':np.asarray(obs['robot_state']['eef']['pos']).tolist(),
            'target_eef_m':self.target[0].tolist(),'red_evidence_sufficient':m['red_pixels']>=200,'uses_object_truth':False})
        self.done=True
        return True

class AlignedCandidateObserver(CandidateObserver):
    """Bounded image alignment to the training view's vertical feature band."""
    def __init__(self,obs):
        super().__init__(obs);self.centering=False;self.alignment_moves=0;self.alignment_steps=0
    def _pixel_error(self,obs):
        m=image_metrics(obs)['views']['image2'];v=m['red_centroid_y_px']
        return None if v is None or m['red_pixels']<150 else ALIGNED_RULE['alignment_target_red_centroid_y_px']-v
    def _set_alignment_target(self,obs,error,first=False):
        current=np.asarray(obs['robot_state']['eef']['pos'])
        if first:
            self.align_anchor=current.copy();self.align_mat=self.Rotation.from_quat(obs['robot_state']['eef']['quat']).as_matrix()
        self.align_target=current.copy();self.align_target[0]+=np.sign(error)*ALIGNED_RULE['alignment_x_increment_m']
        self.align_target[0]=np.clip(self.align_target[0],self.align_anchor[0]-.03,self.align_anchor[0]+.03)
        self.align_target[1:]=self.align_anchor[1:];self.alignment_steps=0
    def action(self,obs):
        if not self.centering:return super().action(obs)
        current=self.Rotation.from_quat(obs['robot_state']['eef']['quat']).as_matrix()
        err=self.Rotation.from_matrix(self.align_mat@current.T).as_rotvec()
        return np.r_[np.clip(.5*(self.align_target-np.asarray(obs['robot_state']['eef']['pos'])),-.006,.006)/.05,
            np.clip(.5*err,-.03,.03)/.5,-1.]
    def update(self,obs):
        if not self.centering:
            event=super().update(obs)
            if self.done:
                error=self._pixel_error(obs)
                if error is not None and abs(error)>ALIGNED_RULE['alignment_tolerance_px']:
                    self.done=False;self.centering=True;self._set_alignment_target(obs,error,first=True)
            return event
        self.alignment_steps+=1
        if self.alignment_steps<ALIGNED_RULE['alignment_steps_per_move']:return False
        self.alignment_moves+=1;error=self._pixel_error(obs)
        self.visits.append({'type':'RGB_pixel_alignment','move':self.alignment_moves,
            'rgb_metrics':image_metrics(obs),'pixel_error_y':error,'actual_eef_m':np.asarray(obs['robot_state']['eef']['pos']).tolist(),
            'target_eef_m':self.align_target.tolist(),'uses_object_truth':False})
        if error is None or abs(error)<=ALIGNED_RULE['alignment_tolerance_px'] or self.alignment_moves>=ALIGNED_RULE['alignment_max_moves']:
            self.done=True
        else:self._set_alignment_target(obs,error)
        return True
