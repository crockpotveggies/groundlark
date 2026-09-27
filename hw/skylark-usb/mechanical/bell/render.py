"""Blender render of the actual enclosure STEP-derived STL solids.

Run: blender --background --python render.py -- --out <export directory>
Electronics are dimension envelopes from enclosure.py, not photographic assets.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[4]
# A distro Blender can share its Python version with the separate CAD environment.
for site in (ROOT/'.local/case-venv/lib').glob('python*/site-packages'):
    sys.path.append(str(site))
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'hw/releases/skylark-bell-r7')
parser.add_argument('--views',nargs='+',choices=['closed.png','open.png','sensor-carrier.png','underside.png','bottom-vents.png','rear.png','rear-detail.png','tray-parts.png'])
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
out=args.out
preview=out/'preview';preview.mkdir(exist_ok=True)
prior=json.loads((preview/'provenance.json').read_text()) if (preview/'provenance.json').exists() else {}
cad_hash=hashlib.sha256((out/'provenance.json').read_bytes()).hexdigest()
if args.views:assert prior.get('cad_provenance_sha256')==cad_hash,'Partial rendering requires unchanged CAD'
rendered=[]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def mat(name,rgb,metal=0,rough=.4):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*rgb,1)
    bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
    return m

materials={'hood':mat('White ASA',(.88,.90,.88)),
 'bottom':mat('Teal ASA',(.025,.27,.29)),
 'carrier':mat('Slate carrier',(.08,.14,.17)),
 'retainer':mat('Orange cell retainer',(.86,.29,.075)),
 'pcb':mat('PCB',(.04,.065,.065)),
 'can':mat('Gas cell body',(.60,.65,.67),.35),
 'face':mat('Gas cell membrane',(.85,.87,.80)),
 'pms':mat('PMS5003 blue shell',(.09,.22,.48),.45),
 'metal':mat('Metal',(.53,.58,.63),.7),
 'component':mat('Package',(.045,.055,.07)),
 'floor':mat('Studio',(.76,.81,.84))}
objects={}
for path in sorted((out/'assembly-parts').glob('*.stl')):
    name=path.stem
    if name in ('fit-coupon','ref-usb-plug-clearance'):continue
    bpy.ops.wm.stl_import(filepath=str(path));o=bpy.context.object;o.name=name
    if name=='hood':key='hood'
    elif name in ('bottom','pms-exhaust-extension') or name.startswith('cable-'):key='bottom'
    elif name in ('pcb-carrier','pms-cradle'):key='carrier'
    elif name=='gas-splash-cover':key='bottom'
    elif name=='cell-retainer':key='retainer'
    elif name=='ref-pcb':key='pcb'
    elif name in ('ref-so2','ref-h2s'):key='can'
    elif name=='ref-pms5003':key='pms'
    elif name in ('ref-component-J1','ref-component-U40'):key='metal'
    else:key='component'
    o.data.materials.append(materials[key]);objects[name]=o
    if name not in ('ref-pcb','bottom','pms-exhaust-extension'):
        bevel=o.modifiers.new('Edge highlights','BEVEL');bevel.width=.18;bevel.segments=2
        bevel.limit_method='ANGLE'
    if hasattr(o.data,'use_auto_smooth'):o.data.use_auto_smooth=True
    o.modifiers.new('Normals','WEIGHTED_NORMAL')

def cylinder(name,x,y,z,r,depth,material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=72,radius=r,depth=depth,location=(x,y,z),rotation=(math.pi/2,0,0))
    o=bpy.context.object;o.name=name;o.data.materials.append(materials[material]);objects[name]=o
    return o

for x,name in [(-21,'SO2'),(21,'H2S')]:
    cylinder(name+' membrane',x,-21.26,106,10.5,.1,'face')
    # Model sockets as conservative cylinders; body-to-PCB gap remains visible.
    for dx,dz in [(0,8.5),(6.0104,6.0104),(-6.0104,6.0104),(0,-8.5)]:
        cylinder(name+' socket '+str((dx,dz)),x+dx,-2.44,106+dz,1.6,4.88,'metal')
for x,z in [(-41,131),(41,131),(-41,39),(41,80)]:cylinder('PCB screw '+str((x,z)),x,-1.5,z,2.7,3,'metal')
for x in (-50,50):cylinder('Retainer screw '+str(x),x,-25.5,106,2.7,3,'metal')

# Cable centerline is illustrative and stays within the reserved USB envelope.
curve=bpy.data.curves.new('USB cable','CURVE');curve.dimensions='3D';curve.bevel_depth=2.2;curve.bevel_resolution=4
s=curve.splines.new('BEZIER');s.bezier_points.add(3)
for p,v in zip(s.bezier_points,[(-10,0,18),(-10,0,-35),(-2,-4,-45),(20,-10,-45)]):
    p.co=v;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
o=bpy.data.objects.new('USB cable',curve);bpy.context.collection.objects.link(o);o.data.materials.append(materials['component'])
objects[o.name]=o

scene=bpy.context.scene;scene.render.engine='CYCLES'
scene.cycles.samples=128;scene.cycles.use_denoising=False
scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.world.color=(.7,.7,.7);scene.view_settings.view_transform='AgX'
bpy.ops.mesh.primitive_plane_add(size=1800,location=(0,0,-48));floor=bpy.context.object
floor.data.materials.append(materials['floor'])
for pos,power,size in [((60,-180,380),2500000,250),((-230,-40,220),1600000,200),((180,250,320),3000000,220)]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size
    o.rotation_euler=(Vector((30,0,75))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam

def render(name,pos,target,scale):
    if args.views and name not in args.views:return
    cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    scene.render.filepath=str(preview/name);bpy.ops.render.render(write_still=True)
    rendered.append(name)

render('closed.png',(265,-350,215),(0,0,60),355)
objects['hood'].location.x=165
render('open.png',(285,-440,290),(65,0,62),450)
objects['hood'].hide_render=True
render('sensor-carrier.png',(230,-390,230),(-5,0,60),305)
# Underside view with the hood back in place and the studio floor hidden.
objects['hood'].hide_render=False;objects['hood'].location.x=0;floor.hide_render=True
render('underside.png',(200,-240,-230),(0,0,52),350)
objects['hood'].hide_render=True
render('bottom-vents.png',(170,-235,-190),(0,0,5),180)
objects['hood'].hide_render=False
floor.hide_render=False
render('rear.png',(-250,360,205),(0,15,60),335)
render('rear-detail.png',(70,350,93),(0,44,83),175)
# Three new printable subassemblies in their exported print orientations.
for o in objects.values():o.hide_render=True
floor.location.z=-1
print_objects=[]
for name,offset,key in [('bottom',(-155,-43,0),'bottom'),
                         ('pms-cradle',(-5,-22,0),'carrier'),
                         ('gas-splash-cover',(85,-37,0),'bottom')]:
    bpy.ops.wm.stl_import(filepath=str(out/(name+'.stl')))
    o=bpy.context.object;o.name='Print pose '+name;o.location=offset
    for polygon in o.data.polygons:polygon.use_smooth=False
    o.data.materials.append(materials[key]);print_objects.append(o)
render('tray-parts.png',(220,-330,320),(12,0,6),425)
for o in print_objects:bpy.data.objects.remove(o,do_unlink=True)
for o in objects.values():o.hide_render=False
floor.location.z=-48
for o in bpy.context.selected_objects:o.select_set(False)
for o in objects.values():o.select_set(True)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
bpy.ops.export_scene.gltf(filepath=str(preview/'skylark-bell.glb'),use_selection=True,export_format='GLB')
report={'renderer':bpy.app.version_string,'source':'STEP-derived enclosure meshes; simplified electronics envelopes; illustrative cables and fasteners',
 'render_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'cad_provenance_sha256':hashlib.sha256((out/'provenance.json').read_bytes()).hexdigest(),
 'images':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(preview.glob('*.png'))}}
report['image_render_source_sha256']={name:(report['render_source_sha256'] if name in rendered else
    prior.get('image_render_source_sha256',{}).get(name,prior.get('render_source_sha256'))) for name in report['images']}
(preview/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
