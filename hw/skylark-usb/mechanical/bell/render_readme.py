"""Studio view of the native Skylark PCB in its STEP-derived tray, beside the bell.

Use official Blender 4.0.2 with OpenImageDenoise, after enclosure.py and the UI
board export (see sw/ui/assets/README.md):
blender --background --python hw/skylark-usb/mechanical/bell/render_readme.py
Source CAD is read-only. Only the README PNG and provenance are written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[4]
# Distro Blender uses the system Python; reuse the separate CAD environment's
# NumPy when its interpreter version matches (no runtime UI dependencies).
site = ROOT/f'.local/case-venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'
if site.exists():
    sys.path.append(str(site))
parser = argparse.ArgumentParser()
parser.add_argument('--cad', type=Path, default=ROOT/'hw/releases/skylark-bell-r7')
parser.add_argument('--samples', type=int, default=256)
parser.add_argument('--width', type=int, default=2400)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
output = ROOT/'docs/images/skylark-assembly.png'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Reject stale board/enclosure exports before making a convincing-looking image.
board_manifest = ROOT/'sw/ui/assets/skylark-provenance.json'
for name, expected in json.loads(board_manifest.read_text())['sha256'].items():
    assert digest(ROOT/name) == expected, f'Stale PCB asset: {name}'
cad_manifest = args.cad/'provenance.json'
cad = json.loads(cad_manifest.read_text())
assert cad['source_sha256'] == digest(Path(__file__).with_name('enclosure.py'))
assert cad['pcb_sha256'] == digest(ROOT/'hw/skylark-usb/boards/skylark-usb/skylark-usb.kicad_pcb')
assert cad['placement_sha256'] == digest(ROOT/'hw/skylark-usb/layout/placement.json')
for name, expected in cad['files'].items():
    assert digest(args.cad/name) == expected, f'Stale mechanical export: {name}'
inputs = [Path(__file__), board_manifest, cad_manifest, Path(__file__).with_name('enclosure.py')]

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def material(name, color, metal=0, rough=.4):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Metallic'].default_value = metal
    node.inputs['Roughness'].default_value = rough
    return mat


materials = {
    'hood': material('White outdoor polymer', (.78, .81, .81), rough=.3),
    'bottom': material('Teal polymer', (.018, .25, .27), rough=.33),
    'carrier': material('Slate polymer', (.10, .19, .22), rough=.36),
    'retainer': material('Warm orange retainer', (.83, .29, .08), rough=.36),
    'pms': material('PMS5003 blue metal shell', (.055, .19, .38), .45, .3),
    'screw': material('Stainless fasteners', (.54, .59, .62), .8, .24),
    'cable': material('USB jacket', (.014, .021, .026), rough=.48),
    'floor': material('Studio floor', (.61, .67, .69), rough=.68),
}
parts = {}
for path in sorted((args.cad/'assembly-parts').glob('*.stl')):
    name = path.stem
    if name == 'fit-coupon' or (name.startswith('ref-') and name != 'ref-pms5003'):
        continue
    inputs.append(path)
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.object
    obj.name = name
    key = ('hood' if name == 'hood' else 'carrier' if name in ('pcb-carrier', 'pms-cradle')
           else 'retainer' if name == 'cell-retainer' else 'pms' if name == 'ref-pms5003' else 'bottom')
    obj.data.materials.append(materials[key])
    bevel = obj.modifiers.new('Small edge highlights', 'BEVEL')
    bevel.width = .12
    bevel.segments = 3
    bevel.limit_method = 'ANGLE'
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.modifiers.new('Weighted face normals', 'WEIGHTED_NORMAL')
    parts[name] = obj
parts['hood'].location = (165, 12, -3)

# Blender's glTF importer maps native Y-up to Z-up. Transform metres to the
# enclosure's millimetres: PCB top-left (-45, 0, 135), front normal toward -Y.
board = ROOT/'sw/ui/assets/skylark.glb'
inputs.append(board)
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(board))
imported = set(bpy.data.objects)-before
pose = Matrix(((1000, 0, 0, -95), (0, 0, -1000, 1.6),
               (0, 1000, 0, 185), (0, 0, 0, 1)))
for obj in imported:
    if obj.parent not in imported:
        obj.matrix_world = pose @ obj.matrix_world


def screw(x, y, z, radius=2.7):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16,
                                       location=(x, y, z))
    obj = bpy.context.object
    obj.name = 'Illustrative M3 button head'
    obj.scale = (radius, 1.1, radius)
    obj.data.materials.append(materials['screw'])
    for polygon in obj.data.polygons:
        polygon.use_smooth = True


for x, z in [(-41, 131), (41, 131), (-41, 39), (41, 80)]:
    screw(x, -1, z)
for x in (-50, 50):
    screw(x, -25.2, 106)

# Cable dressing is illustrative, routed forward to the studio floor.
curve = bpy.data.curves.new('Illustrative USB cable', 'CURVE')
curve.dimensions = '3D'
curve.bevel_depth = 2.2
curve.bevel_resolution = 5
spline = curve.splines.new('BEZIER')
spline.bezier_points.add(4)
for point, coord in zip(spline.bezier_points,
                       [(-10, 0, 18), (-10, 0, -17), (-7, -17, -25.8),
                        (8, -44, -25.8), (35, -52, -25.8)]):
    point.co = coord
    point.handle_left_type = point.handle_right_type = 'AUTO'
obj = bpy.data.objects.new(curve.name, curve)
bpy.context.collection.objects.link(obj)
curve.materials.append(materials['cable'])

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.seed = 17
scene.render.resolution_x = args.width
scene.render.resolution_y = round(args.width*2/3)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.view_settings.view_transform = 'AgX'
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.65, .72, .78, 1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .3
bpy.ops.mesh.primitive_plane_add(size=20000, location=(0, 0, -28))
bpy.context.object.data.materials.append(materials['floor'])
for location, power, size in [((-150, -220, 400), 3400000, 270),
                              ((280, -80, 200), 1900000, 220),
                              ((100, 220, 340), 3600000, 230)]:
    bpy.ops.object.light_add(type='AREA', location=location)
    light = bpy.context.object
    light.data.energy = power
    light.data.shape = 'DISK'
    light.data.size = size
    light.rotation_euler = (Vector((70, 0, 65))-light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(280, -610, 305))
camera = bpy.context.object
camera.rotation_euler = (Vector((77, 0, 65))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 420
camera.data.clip_end = 50000
scene.camera = camera
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .001
scene.render.filepath = str(output)
bpy.ops.render.render(write_still=True)
report = {
    'renderer': f'Blender {bpy.app.version_string} / Cycles',
    'samples': args.samples,
    'denoiser': 'OpenImageDenoise',
    'resolution': [scene.render.resolution_x, scene.render.resolution_y],
    'scope': 'Native PCB and authored component envelopes in STEP-derived Rev G tray; bell beside it. Fasteners and cable dressing illustrative. No physical fit or weather qualification.',
    'pcb_pose': 'PCB top-left (-45,0,135) mm; front normal -Y; rear surface Y=1.6 mm.',
    'sha256': {p.relative_to(ROOT).as_posix(): digest(p) for p in inputs},
    'output_sha256': digest(output),
}
output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
