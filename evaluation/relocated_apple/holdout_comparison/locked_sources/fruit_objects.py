"""Project-owned objects registered via LIBERO's official extension mechanism."""
from pathlib import Path
from robosuite.models.objects import MujocoXMLObject
from libero.libero.envs.base_object import register_object

ROOT = Path(__file__).resolve().parents[1]


class ProjectObject(MujocoXMLObject):
    def __init__(self,name,asset,category):
        super().__init__(str(ROOT/'assets'/asset),name=name,
            joints=[dict(type='free',damping='0.0005')],obj_type='all',
            duplicate_collision_geoms=(category=='fruit_tray'))
        self.category_name = category
        self.rotation = (0,0)
        self.rotation_axis = 'z'
        self.object_properties = {'vis_site_names':{}}


@register_object
class YcbApple(ProjectObject):
    def __init__(self,name='ycb_apple'):
        super().__init__(name,'apple/apple.xml','ycb_apple')


@register_object
class FruitTray(ProjectObject):
    def __init__(self,name='fruit_tray'):
        super().__init__(name,'tray/tray.xml','fruit_tray')
