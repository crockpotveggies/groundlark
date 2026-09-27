"""Skylark bell Rev G: authored CadQuery geometry, millimetres.

X is left/right, -Y faces the gas cells, Z is up. PCB top-left is (-45,0,135).
Build in the original PCB frame, then shift X by +20 to center the finished case.
Print exports are reoriented; assembly STEP retains the installed coordinates.
No electrical files are modified. Run with CadQuery 2.6.1.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import cadquery as cq
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRODUCT = ROOT / 'hw/skylark-usb'
DEFAULT_OUT = ROOT / 'hw/releases/skylark-bell-r7'

def box(x0,y0,z0,x1,y1,z1):
    return cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0,centered=False).translate((x0,y0,z0))

def cz(x,y,z,r,h):
    return cq.Workplane('XY').center(x,y).circle(r).extrude(h).translate((0,0,z))

def cy(x,y,z,r,h):
    return cq.Workplane('XZ').center(x,z).circle(r).extrude(-h).translate((0,y,0))

def hy(x,y,z,af,h):
    return cq.Workplane('XZ').center(x,z).polygon(6,af/math.cos(math.pi/6)).extrude(-h).translate((0,y,0))

def hz(x,y,z,af,h):
    return cq.Workplane('XY').center(x,y).polygon(6,af/math.cos(math.pi/6)).extrude(h).translate((0,0,z))

def rounded(w,d,z,h,r):
    return box(-w/2,-d/2,z,w/2,d/2,z+h).edges('|Z').fillet(r)

def build():
    # Round the upper 25 mm, with a matching inner radius for 3.2 mm walls.
    # Roof-down printing needs support around the curved outer shoulder.
    outer=rounded(130,94,-25,185,12).edges('>Z').fillet(25).translate((-20,0,0))
    void=rounded(123.6,87.6,-26,182.8,8.8).edges('>Z').fillet(21.8).translate((-20,0,0))
    hood=outer.cut(void)
    fasteners=[(x,y) for x in (-75,35) for y in (-35,35)]
    for x,y in fasteners:
        boss=cz(x,y,8,5.5,24)
        edge=-84 if x < -20 else 44
        rib=box(min(x,edge),y-3,8,max(x,edge),y+3,32)
        hood=hood.union(boss.union(rib).intersect(outer))
        # M3 insert nominal OD 4.6 / length 5; tune the bore with the coupon.
        hood=hood.cut(cz(x,y,7.9,2.1,5.2)).cut(cz(x,y,13,1.7,12))

    # Flush rear keyholes; captive-head pockets are closed toward the electronics.
    # Lower the housing 10 mm after putting the heads through the lower circles.
    # A 45-degree lead-in supports each pocket when the hood is printed roof-down.
    for z in (45,125):
        entry=z-10
        pocket=box(-28,36.8,entry-8,-12,44,z+8)
        ramp=(cq.Workplane('YZ').polyline([(36.8,z+8),(44,z+8),(44,z+15.2)])
              .close().extrude(16).translate((-28,0,0)))
        hood=hood.union(pocket).union(ramp)
        head_space=cy(-20,39.4,entry,4.5,4.5).union(cy(-20,39.4,z,4.5,4.5))
        head_space=head_space.union(box(-24.5,39.4,entry,-15.5,43.9,z))
        opening=cy(-20,43.7,entry,4.5,4).union(cy(-20,43.7,z,2.3,4))
        opening=opening.union(box(-22.3,43.7,entry,-17.7,47.7,z))
        hood=hood.cut(head_space).cut(opening)

    # Flat print bed face; open vents drain directly downward.
    # The complete tray now fits inside the skirt for straight downward removal.
    base=rounded(122.4,86.4,0,8,8.2).translate((-20,0,0))
    rim=rounded(122.4,86.4,8,12,8.2).cut(rounded(116.4,80.4,7,14,5.2)).translate((-20,0,0))
    base=base.union(rim)
    for x,y in fasteners:
        base=base.union(cz(x,y,0,5.5,8)).cut(cz(x,y,-1,1.7,10))
        base=base.cut(cz(x,y,-.1,3.2,2.1))
        # Locating lip clears the hood's insert bosses and their wall ribs.
        base=base.cut(cz(x,y,8,6.1,13))
        edge=-84 if x < -20 else 44
        base=base.cut(box(min(x,edge)-.6,y-3.6,8,max(x,edge)+.6,y+3.6,21))

    # One removable cover serves a front-right bank and a rear bank. Keep the
    # cover below the PCB and clear of its carrier; print its broad top face down.
    vent_slots=[(x,-27,x+6,1) for x in (-4,4,12,20)]
    vent_slots += [(3,-34,19,-29),(-48,18,-38,27),(0,18,10,27)]
    vent_slots += [(x,18,x+10,33) for x in (-36,-24,-12)]
    for x0,y0,x1,y1 in vent_slots:base=base.cut(box(x0,y0,-1,x1,y1,9))
    cover=box(-8,-38,26,29,5,29).union(box(-52,10,26,13,36,29))
    cover=cover.union(box(-8,4,26,13,11,29))
    for x,y in [(-4,-34),(25,-34),(-48,32),(9,32)]:
        cover=cover.union(cz(x,y,8,4,21)).cut(cz(x,y,7,1.7,23))
        base=base.cut(cz(x,y,-1,1.7,10)).cut(hz(x,y,5.4,5.7,2.7))
    # Small rim weeps; water cannot collect in the locating lip.
    for x in (-55,-20,15):
        for y in (-42,42):base=base.cut(box(x-2,y-3,6.8,x+2,y+3,10))

    # Carrier feet. Captive M3 nuts are inserted from above before fitting the frame.
    for x in (-61,21):
        base=base.union(box(x-7,17,7,x+7,28,10))
        base=base.cut(cz(x,22,-1,1.7,12)).cut(hz(x,22,7.4,5.7,2.7))

    # Separate left-side cradle: broad face parallel to PCB, ports downward.
    # Full duct walls and an 8 mm retaining collar replace tall thin guides.
    base=base.cut(box(-64,-32,-1,-42,-13,9)).cut(box(-40,-32,-1,-16,-13,9))
    cradle=box(-68,-36,8,-12,-9,22).cut(box(-64,-32,7,-16,-13,23))
    cradle=cradle.union(box(-42,-36,8,-40,-9,21.4))
    collar=box(-68,-36,22,-12,-9,30).cut(box(-65.4,-33.4,21,-14.6,-11.6,31))
    cradle=cradle.union(collar)
    # Stout tie eyes: 8 mm bridges, 3 mm roofs, with an open inner mouth so the
    # strap can turn upward beside the body. Qualify these short bridges in print.
    for y0,y1,g0,g1 in [(-42,-36,-39,-36),(-9,-3,-9,-6)]:
        eye=box(-59,y0,8,-45,y1,16).cut(box(-56,y0-1,10,-48,y1+1,13))
        eye=eye.cut(box(-56,g0,13,-48,g1,17))
        cradle=cradle.union(eye)
    # Two screws enter from above into tray nuts; two enter from below through
    # the exhaust flange and tray into nuts in the cradle tabs.
    for x,y in [(-63,-39),(-65,-6),(-30,-39.5),(-9,-15)]:
        tab=cz(x,y,8,4 if y==-39.5 else 4.5,4)
        if y==-39.5:tab=tab.union(box(x-4.5,y,8,x+4.5,-34,12))
        cradle=cradle.union(tab).cut(cz(x,y,7,1.7,6))
        base=base.cut(cz(x,y,-1,1.7,10))
        if (x,y) in [(-30,-39.5),(-9,-15)]:
            cradle=cradle.cut(hz(x,y,9.4,5.7,2.7))
        else:
            base=base.cut(hz(x,y,5.4,5.7,2.7))
    # Relief in the locating rim admits front tabs and tie eye; floor stays flat.
    base=base.cut(box(-69,-44,8,-24,-35,21))

    # Carry the right-hand PMS exhaust to the skirt edge. The duct and cradle
    # share two fasteners; keep the cable-clamp aperture outside their bolt paths.
    exhaust=box(-42.5,-36,-25,-12,-9,0).cut(box(-40,-33.5,-26,-14.5,-11.5,1))
    for x,y in [(-30,-39.5),(-9,-15)]:
        y0,y1=(-43.5,-35.5) if y==-39.5 else (y-4.5,y+4.5)
        tab=box(x-4.5,y0,-3,x+4.5,y1,0).cut(cz(x,y,-4,1.7,5))
        exhaust=exhaust.union(tab)

    # USB plug access through the bottom, with a separately fitted split cable clamp.
    base=base.cut(box(-39,-5,-1,-21,5,9))
    for x in (-44,-16):
        base=base.cut(cz(x,0,-1,1.7,10)).cut(hz(x,0,5.4,5.7,2.7))
    clamps={}
    for name,x0,x1,sx in [('cable-left',-48,-30,-44),('cable-right',-30,-12,-16)]:
        # Mount below the tray so its main underside stays flat on the print bed.
        plate=box(x0,-9,-3,x1,9,0).cut(cz(-30,0,-4,2.5,5)).cut(cz(sx,0,-4,1.7,5))
        clamps[name]=plate

    # Removable frame stands behind the PCB. Four actual PCB holes are used.
    carrier=None
    for x in (-61,21):
        rail=box(x-5,12,10,x+5,16,138)
        foot=box(x-7,6,10,x+7,29,14).cut(cz(x,22,9,1.7,6))
        # Rear gusset tapers to the vertical rail.
        gusset=(cq.Workplane('YZ').polyline([(16,14),(28,14),(16,35)]).close().extrude(8)
                .translate((x-4,0,0)))
        rail=rail.union(foot).union(gusset)
        carrier=rail if carrier is None else carrier.union(rail)
    # Lower crossbar clears the removable splash cover during vertical assembly.
    carrier=carrier.union(box(-66,12,31,26,16,36)).union(box(-66,12,134,26,16,138))
    mounting=[(-61,131),(21,131),(-61,39),(21,80)]
    for x,z in mounting:
        carrier=carrier.union(cy(x,1.6,z,3.6,10.4)).cut(cy(x,1,z,1.7,16))
        carrier=carrier.cut(hy(x,13.4,z,5.7,3))
    # Side arms are outside the PCB outline and terminate behind the removable retainer.
    carrier=carrier.union(box(-74.5,12,103,34.5,16,109))
    for x in (-70,30):
        carrier=carrier.union(cy(x,-21.5,106,4.5,37.5)).cut(cy(x,-22,106,1.7,39))
        carrier=carrier.cut(hy(x,13.4,106,5.7,3))
    retainer=None
    for x in (-41,1):
        ring=cy(x,-24,106,17.75,2.5).cut(cy(x,-25,106,14,5))
        retainer=ring if retainer is None else retainer.union(ring)
    for x0,x1 in [(-70,-57),(-25,-15),(17,30)]:
        retainer=retainer.union(box(x0,-24,103.5,x1,-21.5,108.5))
    for x in (-70,30):
        retainer=retainer.union(cy(x,-24,106,4.5,2.5)).cut(cy(x,-25,106,1.7,5))

    # Small insert/hole coupon is printed before the large parts.
    coupon=box(0,0,0,50,20,8)
    for i,d in enumerate((3.9,4.0,4.1,4.2,4.3)):
        coupon=coupon.cut(cz(5+10*i,10,2,d/2,7))
    parts={'hood':hood,'bottom':base,'pcb-carrier':carrier,'cell-retainer':retainer,
           'pms-cradle':cradle,'gas-splash-cover':cover,'pms-exhaust-extension':exhaust,**clamps,'fit-coupon':coupon}

    pcb=box(-65,0,35,25,1.6,135).cut(box(15,-1,34,16,3,47))
    for x,z in mounting:pcb=pcb.cut(cy(x,-1,z,1.6,4))
    refs={'pcb':pcb,'so2':cy(-41,-21.19,106,15.75,15.5),
          'h2s':cy(1,-21.19,106,15.75,15.5),'pms5003':box(-65,-33,22,-15,-12,60),
          'usb-plug-clearance':box(-37,-4,13,-23,5,35)}
    # Conservative component bounds from the authored package envelopes and placement.
    dims={'MCU':(7,7,1.75),'ADC':(4.4,5,1.35),'OPA2':(3,3,1.25),
          'OPA1':(1.6,2.9,1.25),'ESD':(1.6,2.9,1.25),'SWITCH':(1.6,2.9,1.25),'AnalogSwitch':(1.6,2.9,1.25),
          'LDO':(1.6,2.9,1.25),'REF':(1.3,2.9,1.25),'JFET':(1.3,2.9,1.25),
          'MOS':(1.3,2.9,1.25),'SHT':(1.5,1.5,.67),'BMP':(2,2,.78),
          'USB':(8.9,7.2,3.15),'PMS':(13.7,5.2,4.1),'BUTTON':(6,6,2.6),
          'FUSE':(3.2,1.6,1.2),'StatusLED':(1.6,.8,.8),'DebugHeader':(4.7,7.6,5.5)}
    placement=json.loads((PRODUCT/'layout/placement.json').read_text())['skylark-usb']
    for row in placement['parts']:
        kind=row['type']
        if kind in (None,'TP','SO2','H2S'):continue
        if kind.startswith('R_'):size=(1.6,.8,.45)
        elif kind.startswith('C_'):size=(2,1.25,1.25) if '0805' in row['local_fp'] else (1.6,.8,.8)
        else:size=dims[kind]
        w,d,h=size;a=math.radians(row['angle'])
        w,d=abs(w*math.cos(a))+abs(d*math.sin(a)),abs(w*math.sin(a))+abs(d*math.cos(a))
        x,z=-65+row['xy'][0],135-row['xy'][1]
        y0,y1=(-h,0) if row['side']=='front' else (1.6,1.6+h)
        refs['component-'+row['ref']]=box(x-w/2,y0,z-d/2,x+w/2,y1,z+d/2)
    return ({name:shape.translate((20,0,0)) for name,shape in parts.items()},
            {name:shape.translate((20,0,0)) for name,shape in refs.items()})

def print_pose(name,shape):
    if name in ('hood','pms-exhaust-extension','gas-splash-cover'):shape=shape.rotate((0,0,0),(1,0,0),180)
    if name=='cell-retainer':shape=shape.rotate((0,0,0),(1,0,0),90)
    b=shape.val().BoundingBox()
    return shape.translate((-b.xmin,-b.ymin,-b.zmin))

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def export_stl(shape,path):
    cq.exporters.export(shape,str(path),tolerance=.07,angularTolerance=.1)
    # OCC's rounded-corner tessellation can collapse triangles to repeated STL
    # vertices. Remove only these degenerate facets; do not fill or repair holes.
    mesh=trimesh.load(path,force='mesh')
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-8))
    mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.body_count==1,('Invalid STL',str(path))
    mesh.export(path)

def export(out):
    out.mkdir(parents=True,exist_ok=True);(out/'assembly-parts').mkdir(exist_ok=True)
    parts,refs=build();assembly=cq.Assembly(name='Skylark_bell_R7')
    for name,shape in parts.items():
        assert shape.val().isValid() and len(shape.solids().vals())==1,name
        export_stl(print_pose(name,shape),out/(name+'.stl'))
        cq.exporters.export(shape,str(out/(name+'.step')))
        export_stl(shape,out/'assembly-parts'/(name+'.stl'))
        if name!='fit-coupon':assembly.add(shape,name=name,color=cq.Color(.91,.93,.91) if name=='hood' else cq.Color(.02,.36,.39))
    for name,shape in refs.items():
        export_stl(shape,out/'assembly-parts'/('ref-'+name+'.stl'))
        if name!='usb-plug-clearance':assembly.add(shape,name=name,color=cq.Color(.15,.17,.18))
    assembly.save(str(out/'skylark-bell-assembly.step'))
    report={'generator':'hw/skylark-usb/mechanical/bell/enclosure.py','cadquery':cq.__version__,
            'pcb_sha256':digest(PRODUCT/'boards/skylark-usb/skylark-usb.kicad_pcb'),
            'placement_sha256':digest(PRODUCT/'layout/placement.json'),
            'source_sha256':digest(Path(__file__)),'units':'mm',
            'body_mm':[130,94,185],'roof_outer_radius_mm':25,'roof_inner_radius_mm':21.8,
            'gas_bottom_vent_area_mm2':1382,'gas_baffle_gap_mm':18,
            'pms_orientation':'50 x 38 face parallel to PCB; ports down',
            'skirt_below_tray_mm':25,'mount':'two flush M4 keyholes',
            'mount_pitch_mm':80,'mount_drop_mm':10,'entry_diameter_mm':9,
            'shaft_slot_mm':4.6,'head_envelope_max_mm':[8,3.5],
            'scope':'Engineering prototype. Simplified electronics envelopes; no weather/thermal/flow qualification.',
            'files':{p.name:digest(p) for p in sorted(out.glob('*')) if p.suffix in ('.stl','.step')}}
    (out/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'exported':str(out),'printed_parts':len(parts)},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    export(parser.parse_args().out)
