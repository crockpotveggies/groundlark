"""Render actual printed solids; electronics are clearly attributed references."""
import argparse,bpy,math,json,sys
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'hw/releases/groundlark-case-r1'
CACHE=ROOT/'.local/case'
REF=CACHE/'reference'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--view',default='all',choices=('all','assembly-open','assembly-closed','cover-top','cover-interior'))
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
for site in (ROOT/'.local/case-venv/lib').glob('python*/site-packages'):sys.path.append(str(site))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def mat(name,rgba,metal=0,rough=.4):
 m=bpy.data.materials.new(name);m.diffuse_color=(*rgba,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*rgba,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 return m
materials={
 'base':mat('PETG deep teal',(.045,.17,.20),rough=.62),
 'cover':mat('PETG teal',(.07,.22,.25),rough=.62),
 'orange':mat('PETG clamp',(.95,.34,.07),rough=.62),
 'pcb':mat('PCB green',(.025,.25,.11)),
 'black':mat('IC and connector',(.025,.032,.04)),
 'metal':mat('Metal',(.55,.61,.65),.75,.28),
 'can':mat('Geophone can',(.48,.42,.23),.65,.3),
 'floor':mat('Studio',(.83,.87,.89)),
 'red':mat('Red wire',(.6,.018,.01)),
}

def stl(path,material):
 before=set(bpy.data.objects);bpy.ops.wm.stl_import(filepath=str(path))
 obj=next(o for o in bpy.data.objects if o not in before);obj.data.materials.clear();obj.data.materials.append(materials[material]);return obj

def cube(name,lo,hi,material):
 bpy.ops.mesh.primitive_cube_add(size=1,location=tuple((a+b)/2 for a,b in zip(lo,hi)));o=bpy.context.object;o.name=name;o.dimensions=tuple(b-a for a,b in zip(lo,hi));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(materials[material]);return o

def cyl(name,xy,z,r,h,material):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=h,location=(*xy,z+h/2));o=bpy.context.object;o.name=name;o.data.materials.append(materials[material]);return o

def wire(name,pts,material,r=.6):
 curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.resolution_u=20;curve.bevel_depth=r;curve.bevel_resolution=3
 s=curve.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for p,v in zip(s.bezier_points,pts):p.co=v;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 o=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(o);o.data.materials.append(materials[material]);return o
base=stl(REF/'base-assembled.stl','base');cover=stl(REF/'cover-assembled.stl','cover')
stl(REF/'geophone-jaw-assembled.stl','orange');stl(REF/'cable-clamp-assembled.stl','orange')
for path in REF.glob('reference-*.stl'):
 name=path.stem[10:]
 if name in ('hat','fpga','geophone_terminals','geophone_plug','fpga_heatsink','j83'):continue
 material='pcb' if name=='pi' else ('can' if name=='geophone' else 'black' if name=='gpio_stack' else 'metal')
 stl(path,material)
# Missing custom VRML connector bodies are provided as envelope boxes.
for x,y,w,d in [(55,12,30.2,4.6),(55,44,30.2,4.6),(34,28,4.6,20.2)]:
 cube('Trenz mating connector',(x-w/2,y-d/2,40.379),(x+w/2,y+d/2,44.379),'black')
# Actual generated HAT model. glTF Y-up becomes Blender Z-up on import.
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'sw/ui/assets/daqhat-01.glb'))
new=[o for o in bpy.data.objects if o not in before]
# Bake original world poses first, then detach hierarchy before global transform.
world={o:o.matrix_world.copy() for o in new}
transform=Matrix(((1000,0,0,-50),(0,-1000,0,-50),(0,0,1000,40.379-1.4684),(0,0,0,1)))
for o in new:
 o.parent=None;o.matrix_world=transform@world[o]
# Manufacturer TE0712 geometry, individually tessellated and approximately colored.
for item in json.loads((CACHE/'fpga-bodies.json').read_text()):stl(CACHE/(item['name']+'.stl'),item['color'])
# Bare geophone terminals and wiring are illustrative within the reserved envelope.
cyl('Geophone top',(42,-25),40.8,12.4,.7,'black')
for x in (37,47):cyl('Illustrative terminal',(x,-25),41.5,.7,5,'metal')
wire('Geophone positive',[(37,-25,46),(51,-31,49),(65,-32,35),(69.5,-26,12),(69.5,-18,9)],'red',.55)
wire('Geophone negative',[(47,-25,46),(56,-28,48),(68,-31,34),(70.5,-26,12),(70.5,-18,9)],'black',.55)
wire('Shielded lead to J90',[(70,-18,9),(62,-9,18),(-2,-5,45),(-2,22,48),(5,45,58),(14,51,59)],'black',1.6)
# Captive nut/screw representations; not printable components.
for yy in (-43.2,-6.8):
 o=cyl('M3 geophone screw',(0,0),0,2.75,3,'metal');o.rotation_euler[1]=math.pi/2;o.location=(33.5,yy,19)
for x,y in [(0,-34),(86,-34),(43,59)]:cyl('Metal leveling contact',(x,y),-5,3.5,5,'metal')
for x in (64.8,75.2):cyl('Cable clamp screw',(x,-23),13,2.75,2.5,'metal')
# Render settings.
# Preserve planar CAD faces; smooth STL normals create swollen edges and waves.
for obj in bpy.context.scene.objects:
 if obj.type=='MESH':
  for face in obj.data.polygons:face.use_smooth=False
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True
scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.75,.80,.85,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
cube('Studio floor',(-400,-400,-6),(500,400,-5.7),'floor')
for name,pos,power,size in [('Key',(30,-130,250),650000,180),('Fill',(-140,70,180),350000,150),('Rim',(250,100,190),500000,130)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((60,0,25))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam

def render(name,pos,target,scale):
 if args.view!='all' and name!=args.view+'.png':return
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 scene.render.filepath=str(OUT/'preview'/name);bpy.ops.render.render(write_still=True)
cover.location.x=125
render('assembly-open.png',(295,-300,270),(104,4,29),320)
cover.location.x=0
render('assembly-closed.png',(225,260,205),(42,6,37),235)
# Save an interactive assembly model without studio elements/lights/camera.
for o in bpy.context.selected_objects:o.select_set(False)
for o in scene.objects:
 if o.type=='MESH' and o.name!='Studio floor':o.select_set(True)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
bpy.ops.export_scene.gltf(filepath=str(OUT/'preview/case-assembly.glb'),use_selection=True,export_format='GLB')
# A lid-only top view makes the mark and the space between vents easy to inspect.
for obj in scene.objects:
 if obj.type in ('MESH','CURVE') and obj!=cover and obj.name!='Studio floor':obj.hide_render=True
render('cover-top.png',(43,7,300),(43,7,0),180)
cover.matrix_world=Matrix.Translation((0,14,75))@Matrix.Rotation(math.pi,4,'X')
render('cover-interior.png',(230,-250,280),(43,7,35),235)
print('Rendered CAD views and exported interactive assembly')
