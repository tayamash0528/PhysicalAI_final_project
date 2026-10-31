"""Convert the preserved YCB apple to OBJ; generate an explicit simple rigid tray."""
import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy', required=True, type=Path)
    args = parser.parse_args()
    dest = Path('assets/apple')
    dest.mkdir(parents=True, exist_ok=True)
    source = args.legacy/'models/ycb_apple/meshes/apple.dae'
    root = ET.parse(source).getroot()
    ns = {'c': 'http://www.collada.org/2005/11/COLLADASchema'}
    arrays = {s.attrib['id']: [float(x) for x in s.find('c:float_array', ns).text.split()]
              for s in root.findall('.//c:mesh/c:source', ns)}
    p = arrays['positions']
    # Original was shifted to sit on z=0. Center it for a dynamic free body.
    lo = [min(p[i::3]) for i in range(3)]
    hi = [max(p[i::3]) for i in range(3)]
    center = [(a+b)/2 for a,b in zip(lo,hi)]
    triangles = root.find('.//c:triangles/c:p', ns)
    indices = [int(x) for x in triangles.text.split()]
    with (dest/'apple.obj').open('w') as f:
        f.write('# YCB 013_apple, CC BY 4.0; converted from preserved COLLADA\n')
        for j in range(0, len(p), 3):
            f.write('v '+' '.join(f'{p[j+i]-center[i]:.7f}' for i in range(3))+'\n')
        uv = arrays['uv']
        for j in range(0, len(uv), 2):
            f.write(f'vt {uv[j]:.7f} {uv[j+1]:.7f}\n')
        for j in range(0,len(indices),9):
            f.write('f '+' '.join(f'{indices[j+k]+1}/{indices[j+k+2]+1}' for k in (0,3,6))+'\n')
    shutil.copy2(source.parent/'texture_map.png', dest/'texture.png')
    apple_xml = '''<mujoco model="ycb_apple">
  <asset>
    <texture name="apple_tex" type="2d" file="texture.png"/>
    <material name="apple_mat" texture="apple_tex" specular="0.15" shininess="0.1"/>
    <mesh name="apple_mesh" file="apple.obj"/>
  </asset>
  <worldbody><body><body name="object">
    <geom name="collision" type="ellipsoid" size="0.036 0.036 0.034" mass="0.15" friction="1.0 0.01 0.001" group="0" rgba="0.8 0.1 0.1 0"/>
    <geom name="visual" type="mesh" mesh="apple_mesh" material="apple_mat" contype="0" conaffinity="0" group="1" mass="0"/>
  </body>
  <site name="bottom_site" pos="0 0 -0.036" size="0.005" rgba="0 0 0 0"/>
  <site name="top_site" pos="0 0 0.036" size="0.005" rgba="0 0 0 0"/>
  <site name="horizontal_radius_site" pos="0.039 0.039 0" size="0.005" rgba="0 0 0 0"/>
  </body></worldbody>
</mujoco>'''
    (dest/'apple.xml').write_text(apple_xml)
    tray = Path('assets/tray')
    tray.mkdir(parents=True,exist_ok=True)
    tray_xml = '''<mujoco model="fruit_tray"><worldbody><body><body name="object">
      <geom name="bottom" type="box" pos="0 0 0" size="0.080 0.080 0.004" mass="0.4" friction="1 0.01 0.001" rgba="0.75 0.78 0.82 1" group="0"/>
      <geom name="left" type="box" pos="-0.077 0 0.014" size="0.003 0.08 0.018" mass="0.05" rgba="0.75 0.78 0.82 1" group="0"/>
      <geom name="right" type="box" pos="0.077 0 0.014" size="0.003 0.08 0.018" mass="0.05" rgba="0.75 0.78 0.82 1" group="0"/>
      <geom name="front" type="box" pos="0 -0.077 0.014" size="0.074 0.003 0.018" mass="0.05" rgba="0.75 0.78 0.82 1" group="0"/>
      <geom name="back" type="box" pos="0 0.077 0.014" size="0.074 0.003 0.018" mass="0.05" rgba="0.75 0.78 0.82 1" group="0"/>
      </body>
      <site name="bottom_site" pos="0 0 -0.004" size="0.005" rgba="0 0 0 0"/>
      <site name="top_site" pos="0 0 0.032" size="0.005" rgba="0 0 0 0"/>
      <site name="horizontal_radius_site" pos="0.113 0.113 0" size="0.005" rgba="0 0 0 0"/>
      </body></worldbody></mujoco>'''
    (tray/'tray.xml').write_text(tray_xml)
    manifest = {'apple': {'source':'YCB 013_apple Google 16k scan',
        'license':'CC BY 4.0', 'mesh_dimensions_m':[b-a for a,b in zip(lo,hi)],
        'mass_kg':0.15,'collision':'ellipsoid approximation, radii 0.036 0.036 0.034 m',
        'friction':[1.0,0.01,0.001], 'deformation_or_damage_model':False},
        'tray':{'inner_xy_bounds_m':[[-0.074,-0.074],[0.074,0.074]],
                'bottom_top_z_m':0.004, 'wall_top_z_m':0.032},
        'files':{str(p).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in Path('assets').rglob('*') if p.is_file() and p.name!='manifest.json'}}
    Path('assets/manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__': main()
