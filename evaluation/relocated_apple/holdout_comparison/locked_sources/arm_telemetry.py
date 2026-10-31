"""Evaluation-only simulator measurements. Never returns observations to a policy."""
import json
import numpy as np
import mujoco


class ArmTelemetry:
    VERSION='arm_telemetry_v3_includes_all_leaf_contacts'
    def __init__(self,env,target='apple_1',center_local=(0,0,0)):
        self.env=env;self.sim=env._env.sim;self.robot=env._env.robots[0]
        self.obj=env._env.env.objects_dict[target]
        self.body=self.sim.model.body_name2id(self.obj.root_body)
        self.initial_pos=self.sim.data.body_xpos[self.body].copy()
        self.center_local=np.asarray(center_local,dtype=float)
        self.initial_center=self.initial_pos+self.sim.data.body_xmat[self.body].reshape(3,3)@self.center_local
        self.left={self.sim.model.geom_name2id(n) for n in self.robot.gripper.important_geoms['left_finger']}
        self.right={self.sim.model.geom_name2id(n) for n in self.robot.gripper.important_geoms['right_finger']}
        self.left_pad=[self.sim.model.geom_name2id(n) for n in self.robot.gripper.important_geoms['left_fingerpad']]
        self.right_pad=[self.sim.model.geom_name2id(n) for n in self.robot.gripper.important_geoms['right_fingerpad']]
        self.table=self.sim.model.geom_name2id('table_collision')
        self.arm_joints=[self.sim.model.joint_name2id(n) for n in self.robot.robot_model.joints]
        self.table_top=float(self.sim.data.geom_xpos[self.table,2]+self.sim.model.geom_size[self.table,2])
        self.hold=0;self.stage_counts={}

    def metadata(self):
        return {'version':self.VERSION,'position_units':'metre','force_units':'newton',
            'time_units':'simulation second','world_z_up':True,'table_top_world_z_m':self.table_top,
            'initial_object_root_world_m':self.initial_pos.tolist(),
            'measured_center_local_m':self.center_local.tolist(),
            'initial_object_center_height_above_table_m':float(self.initial_center[2]-self.table_top),
            'object_mass_kg':float(self.sim.model.body_mass[self.body]),
            'robot_joint_limits_rad':self.sim.model._model.jnt_range[self.arm_joints].tolist(),
            'initial_reference':'settled pose immediately before the first logged control action',
            'contact_sampling':'end of every 20Hz control step; transient substep contacts may be missed',
            'lift_success_threshold_m':.05,'continuous_hold_seconds':2,'required_hold_steps':40}

    def sample(self,step,action,obs,phase='vla'):
        sim=self.sim;root=sim.data.body_xpos[self.body].copy()
        pos=root+sim.data.body_xmat[self.body].reshape(3,3)@self.center_local
        eef=np.asarray(obs['robot_state']['eef']['pos'])
        lp=np.mean(sim.data.geom_xpos[self.left_pad],axis=0)
        rp=np.mean(sim.data.geom_xpos[self.right_pad],axis=0)
        contacts=[];left=False;right=False;leaf_contacts=[]
        for i in range(sim.data.ncon):
            c=sim.data.contact[i];g1=int(c.geom1);g2=int(c.geom2)
            names=[sim.model.geom_id2name(g1) or '',sim.model.geom_id2name(g2) or '']
            if any('observation_leaf' in name for name in names):
                wrench=np.zeros(6);mujoco.mj_contactForce(sim.model._model,sim.data._data,i,wrench)
                other=names[1] if 'observation_leaf' in names[0] else names[0]
                leaf_contacts.append({'geom1':names[0],'geom2':names[1],
                    'other_kind':'apple' if 'apple_1' in other else 'robot' if ('robot' in other or 'gripper' in other) else 'environment',
                    'signed_distance_m':float(c.dist),'normal_force_N':float(wrench[0])})
            if self.body not in [int(sim.model.geom_bodyid[g1]),int(sim.model.geom_bodyid[g2])]:continue
            other=g2 if int(sim.model.geom_bodyid[g1])==self.body else g1
            side='left' if other in self.left else ('right' if other in self.right else 'other')
            left|=side=='left';right|=side=='right'
            wrench=np.zeros(6)
            mujoco.mj_contactForce(sim.model._model,sim.data._data,i,wrench)
            contacts.append({'geom1':sim.model.geom_id2name(g1),'geom2':sim.model.geom_id2name(g2),
                'side':side,'signed_distance_m':float(c.dist),'normal_force_N':float(wrench[0])})
        lift=float(pos[2]-self.initial_center[2]);bilateral=left and right
        self.hold=self.hold+1 if lift>=.05 and bilateral else 0
        q=np.asarray(obs['robot_state']['gripper']['qpos'])
        arm_q=np.asarray(obs['robot_state']['joints']['pos'])
        limits=sim.model._model.jnt_range[self.arm_joints]
        stages={'approach_within_50mm_padmid':float(np.linalg.norm((lp+rp)/2-pos))<.05,
                'close_command':float(action[-1])>0,'strong_close_command':float(action[-1])>.5,
                'left_contact':left,'right_contact':right,
                'bilateral_contact':bilateral,'lift_50mm':lift>=.05,
                'lift_50mm_hold_2s_bilateral':self.hold>=40}
        for key,value in stages.items():self.stage_counts[key]=self.stage_counts.get(key,0)+int(value)
        return {'step':step,'phase':phase,'simulation_time_s':float(sim.data.time),
            'object_root_world_m':root.tolist(),'object_measured_center_world_m':pos.tolist(),
            'object_com_world_m':sim.data._data.xipos[self.body].tolist(),
            'eef_world_m':eef.tolist(),'left_pad_center_world_m':lp.tolist(),'right_pad_center_world_m':rp.tolist(),
            'eef_to_object_m':float(np.linalg.norm(eef-pos)),
            'padmid_to_object_m':float(np.linalg.norm((lp+rp)/2-pos)),
            'object_world_z_m':float(pos[2]),'object_center_above_table_m':float(pos[2]-self.table_top),
            'object_lift_from_initial_m':lift,'gripper_qpos_m':q.tolist(),
            'joint_aperture_m':float(np.abs(q).sum()),'pad_center_separation_m':float(np.linalg.norm(lp-rp)),
            'gripper_command':float(action[-1]),'contacts':contacts,'leaf_contacts':leaf_contacts,'stages':stages,
            'robot_joint_positions_rad':arm_q.tolist(),
            'robot_joint_limit_margins_rad':np.minimum(arm_q-limits[:,0],limits[:,1]-arm_q).tolist(),
            'lift_hold_steps':self.hold,'stage_counts_so_far':dict(self.stage_counts)}
