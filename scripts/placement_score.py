"""Evaluation-only tray containment; never imported by observation/target selection."""
import numpy as np


def gripper_released(qpos, command):
    # Panda has opposed finger joint signs; require an open command and near-full gap.
    return float(command) < -0.5 and float(np.abs(qpos).sum()) >= 0.075


def contained(center_world, rotation_world, vertices_local, tray_pos, tray_rotation,
              bounds=(-0.074,0.074,-0.074,0.074), floor=0.004, wall_top=0.032):
    # Require all fruit footprint vertices inside the tray, not just its center.
    world = np.asarray(vertices_local) @ np.asarray(rotation_world).T + np.asarray(center_world)
    local = (world - np.asarray(tray_pos)) @ np.asarray(tray_rotation)
    xmin,xmax,ymin,ymax = bounds
    footprint = bool(np.all((local[:,0] >= xmin) & (local[:,0] <= xmax) &
                            (local[:,1] >= ymin) & (local[:,1] <= ymax)))
    # Resting object must have its lowest point near the tray floor.
    supported = floor-0.006 <= float(local[:,2].min()) <= floor+0.012
    return footprint and supported


class PlacementHold:
    def __init__(self, seconds=2.0, hz=20):
        self.required_steps = round(seconds*hz)
        self.streak = 0
        self.success = False

    def update(self, inside, gripper_open):
        self.streak = self.streak+1 if inside and gripper_open else 0
        self.success = self.streak >= self.required_steps
        return self.success
