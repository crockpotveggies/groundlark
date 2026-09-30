"""Groundlark printable case. Board inputs use native HAT XY; lengths are mm.

Authoring coordinates follow KiCad (Y down). build() converts once to physical
Z-up assembly coordinates (X right, Y opposite CAD). Native 3D component models
already use a right-handed basis and must NEVER be reflected on import.

CadQuery solids are manufacturing geometry. Electronics are reference envelopes,
not printable parts. Does not open or modify electrical source/CAD.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import cadquery as cq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOGO = ROOT/'hw/shared/libraries/Groundlark.pretty/Logo_Groundlark_7mm.kicad_mod'


def stack_xy(c,x,y):
    """Rotate about the fixed 85 x 56 mm Pi footprint, including the wider HAT in the fixed enclosure coordinates."""
    angle=c['stack_rotation_deg']
    if angle not in (0,180):raise ValueError('Stack rotation must be 0 or 180 degrees')
    return (85-x,56-y) if angle==180 else (x,y)


def stack_pose(c,solid):
    stack_xy(c,0,0)  # Validate the supported orientations.
    return solid.rotate((42.5,28,0),(42.5,28,1),c['stack_rotation_deg'])


def bird_mark(center, height, z, depth):
    """Extrude the shared favicon artwork, retaining its eye/wing/leg holes."""
    points=[tuple(map(float,p)) for p in re.findall(r'\(xy ([^ ]+) ([^)]+)\)',LOGO.read_text())]
    # KiCad encodes holes with doubled bridges in one polygon. Unwind those
    # bridges into separate closed wires for the CAD face.
    stack=[];holes=[]
    for point in points:
        if point in stack:
            index=stack.index(point)
            loop=stack[index:]
            if len(loop)>2:holes.append(loop)
            stack=stack[:index+1]
        else:stack.append(point)
    xmin=min(p[0] for p in points);xmax=max(p[0] for p in points)
    ymin=min(p[1] for p in points);ymax=max(p[1] for p in points)
    scale=height/(ymax-ymin)
    def wire(loop):
        # Keep native Y-down here; build() converts the finished assembly once.
        return cq.Wire.makePolygon([cq.Vector(center[0]+(x-(xmin+xmax)/2)*scale,
                                             center[1]+(y-(ymin+ymax)/2)*scale,z)
                                    for x,y in loop],close=True)
    return cq.Workplane(obj=cq.Solid.extrudeLinear(wire(stack),[wire(h) for h in holes],cq.Vector(0,0,depth)))


def box(x0,y0,z0,x1,y1,z1):
    return cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0,centered=False).translate((x0,y0,z0))


def cylinder(x,y,z,r,h):
    return cq.Workplane('XY').center(x,y).circle(r).extrude(h).translate((0,0,z))


def hex_z(x,y,z,af,h):
    return cq.Workplane('XY').center(x,y).polygon(6,af/math.cos(math.pi/6)).extrude(h).translate((0,0,z))


def hole_x(x0,y,z,r,length):
    return cq.Workplane('YZ').center(y,z).circle(r).extrude(length).translate((x0,0,0))


def hole_y(x,y0,z,r,length):
    return cq.Workplane('XZ').center(x,z).circle(r).extrude(length).translate((0,y0+length,0))


def rounded(bounds,z,h,r):
    x0,y0,x1,y1=bounds
    return box(x0,y0,z,x1,y1,z+h).edges('|Z').fillet(r)


def build(c):
    x0,y0,x1,y1=c['outer']; floor=c['floor']; roof=c['roof_z']; w=c['wall']
    pi_bottom=c['pi_bottom_z']; pi_top=pi_bottom+c['pcb_thickness']
    hat_bottom=pi_top+c['pi_to_hat_gap']; hat_top=hat_bottom+c['pcb_thickness']
    fpga_bottom=hat_top+c['hat_to_fpga_gap']; fpga_top=fpga_bottom+c['pcb_thickness']
    base=rounded(c['outer'],0,floor,c['corner_radius'])
    for x,y in c['pi_holes']:
        x,y=stack_xy(c,x,y)
        base=base.union(cylinder(x,y,floor,3,pi_bottom-floor))
        base=base.cut(cylinder(x,y,-.1,1.4,pi_bottom+.2))
        base=base.cut(cylinder(x,y,-.1,2.7,3.1))
    # Cover screws enter from below; nuts are captive in the cover's lower face.
    for x,y in c['case_screws']:
        base=base.cut(cylinder(x,y,-.1,1.7,floor+.2))
        base=base.cut(cylinder(x,y,-.1,3.1,2.6))
    for x,y in c['leveling_feet']:
        base=base.cut(cylinder(x,y,-.1,2.2,floor+.2))
        base=base.cut(hex_z(x,y,1.7,7.3,floor-1.6))
    gx,gy=c['geophone_center']; seat=c['geophone_seat_z']
    r=(c['geophone_diameter']+c['geophone_diametral_clearance'])/2
    outer=r+c['geophone_clamp_wall']; split=c['geophone_split_gap']/2
    h=c['geophone_clamp_height']
    pedestal=cylinder(gx,gy,floor,outer,seat-floor)
    ring=cylinder(gx,gy,seat,outer,h).cut(cylinder(gx,gy,seat-.1,r,h+.2))
    # Integrated right half plus removable left jaw; through-bolts along X.
    ears=[]
    for yy in (gy-18.2,gy+18.2):
        ear=box(gx-7,yy-4.6,seat,gx+7,yy+4.6,seat+h)
        ring=ring.union(ear)
        ears.append(yy)
    right=ring.intersect(box(gx+split,gy-24,seat-.1,gx+25,gy+24,seat+h+.1))
    jaw=ring.intersect(box(gx-25,gy-24,seat-.1,gx-split,gy+24,seat+h+.1))
    for yy in ears:
        drill=hole_x(gx-9,yy,seat+h/2,1.7,18)
        right=right.cut(drill);jaw=jaw.cut(drill)
        # M3 nut trap, accessible from the right with the cover removed.
        nut=cq.Workplane('YZ').center(yy,seat+h/2).polygon(6,5.8/math.cos(math.pi/6)).extrude(2.7).translate((gx+4.4,0,0))
        right=right.cut(nut)
    base=base.union(pedestal).union(right)
    # Geophone cable clamp: capture M3 nuts from above, before fitting its cap.
    # Raised clamp beside the withdrawal corridor: lead stays at connector level.
    cable_z=hat_top+3.6
    base=base.union(box(55,-36,floor,63,-16,cable_z))
    cap=box(55,-36,cable_z,63,-16,cable_z+5)
    channel=hole_x(54,-26,cable_z,c['cable_diameter']/2,10)
    base=base.cut(channel);cap=cap.cut(channel)
    for y in (-31.2,-20.8):
        base=base.cut(cylinder(59,y,cable_z-5.5,1.7,5.6)).cut(hex_z(59,y,cable_z-2.6,5.8,2.7))
        cap=cap.cut(cylinder(59,y,cable_z-.1,1.7,5.2))
    # Columns stand beyond the Pi plug corridors. Thick cantilever ledges
    # reach under the power wing above the port/cable height.
    for ya,yb,la,lb in ((-6,-.3,-1,4),(56.3,62,52,57)):
        column=box(101,ya,floor,107,yb,hat_bottom-2)
        ledge=box(104,la,pi_top+20,110,lb,hat_bottom)
        base=base.union(stack_pose(c,column)).union(stack_pose(c,ledge))
    for ya,yb in ((-3.3,-.3),(56.3,59.3)):
        stop=box(104,ya,hat_bottom-2,107,yb,hat_top+.5)
        base=base.union(stack_pose(c,stop))
    # Additional bearing saddles and edge stops for the Pi supervisor wing.
    for ya,yb,la,lb in ((-6,-.3,-1,4),(56.3,62,52,57)):
        base=base.union(stack_pose(c,box(131,ya,floor,137,yb,hat_bottom-2)))
        base=base.union(stack_pose(c,box(134,la,pi_top+20,140,lb,hat_bottom)))
    for ya,yb in ((-3.3,-.3),(56.3,59.3)):
        base=base.union(stack_pose(c,box(134,ya,hat_bottom-2,137,yb,hat_top+.5)))
    cover=rounded(c['outer'],floor,roof+c['roof_thickness']-floor,c['corner_radius'])
    cover=cover.cut(rounded([x0+w,y0+w,x1-w,y1-w],floor-.1,roof-floor+.1,2))
    for x,y in c['case_screws']:
        cover=cover.union(cylinder(x,y,floor,5,roof-floor))
        cover=cover.cut(hex_z(x,y,floor-.1,5.8,2.7))
        cover=cover.cut(cylinder(x,y,floor-.1,1.7,10.1))
    # Enlarged entry bays admit cable overmoulds past the recessed Pi ports.
    ports={
      'usb_ethernet':box(84,0,floor-.1,85-x0+1,57,pi_top+18),
      'power_hdmi_audio':box(3,50,floor-.1,63,y1+1,pi_top+11),
      'microsd':box(x0-1,19,floor-.1,9,37,pi_bottom+1.5),
    }
    for cut in ports.values():cover=cover.cut(stack_pose(c,cut))
    if c['stack_rotation_deg']==180:
        # Pi power/HDMI/audio now face the geophone bay. These are cable exits;
        # plug access requires removing the lid and routing around the sensor.
        cover=cover.cut(box(22,y0-1,floor-.1,82,0,pi_top+11))
    # Rear, bottom-open slot admits a <=14 mm DC overmould and allows cover
    # removal while connected. Jack is recessed 7.2 mm from the inner wall.
    cover=cover.cut(box(-18,54,floor-.1,-2,y1+1,hat_top+14.5))
    # Separate, keyed two-pole battery plug; bottom-open for cover removal.
    cover=cover.cut(box(-40,52,floor-.1,-24,y1+1,hat_top+13))
    for xx in (-40,-24):base=base.cut(box(xx-1,57,-.1,xx+1,61,floor+.1))
    # Lid-off switch operation or insulated probe through the roof service slot.
    cover=cover.cut(box(-25,41,roof-.1,-15,51,roof+c['roof_thickness']+.1))
    # Power-lead tie slots belong to the base so the cover lifts off freely.
    for xx in (-17,-3):base=base.cut(box(xx-1,57,-.1,xx+1,61,floor+.1))
    # Roof vents: 3 mm bridge spans when printed roof-down.
    for x in range(6,82,7):
        cover=cover.cut(box(x,8,roof-.1,x+3,48,roof+3.1))
    for x in (-54,-47,-40,-33,-24,-17,-10):
        cover=cover.cut(box(x,9,roof-.1,x+3,35,roof+c['roof_thickness']+.1))
    # Separate small vents above geophone terminals, away from its clamp.
    for x in range(28,57,7):
        cover=cover.cut(box(x,-33,roof-.1,x+3,-18,roof+3.1))
    # Low/high side convection openings; roof-down printing bridges 3 mm.
    for yy in (-38,-30,-22):
        for z in (18,58):cover=cover.cut(box(x0-1,yy,z,x0+w+.1,yy+3,z+9))
    for xx in (6,16,26,56,66,76):
        vent_z=32 if c['stack_rotation_deg']==180 else 18
        cover=cover.cut(box(xx,y0-1,vent_z,xx+3,y0+w+.1,vent_z+14))
    # Recessed bird centered in the 26 mm strip between the roof vent groups.
    cover=cover.cut(bird_mark((43,-5),20,roof+c['roof_thickness']-.6,.65))
    # Small bore coupon uses the same split clamp cross-section; no hardware needed.
    coupon=cylinder(0,0,0,outer,6).cut(cylinder(0,0,-.1,r,6.2))
    coupon=coupon.cut(box(-.5,-outer-1,-.1,.5,-r+.5,6.1))
    # Rigid bodies and conservative service envelopes for collision checks.
    pi=box(0,0,pi_bottom,85,56,pi_top)
    hat=box(0,0,hat_bottom,*c['hat_size'],hat_top)
    for x,y in c['pi_holes']:
        pi=pi.cut(cylinder(x,y,pi_bottom-.1,1.35,2))
        hat=hat.cut(cylinder(x,y,hat_bottom-.1,1.35,2))
    fpga=box(30,8,fpga_bottom,80,48,fpga_top)
    for x,y in c['trenz_holes']:fpga=fpga.cut(cylinder(x,y,fpga_bottom-.1,1.6,2))
    ref={'pi':pi,'hat':hat,'fpga':fpga,
      'geophone':cylinder(gx,gy,seat,c['geophone_diameter']/2,c['geophone_height']),
      'geophone_terminals':cylinder(gx,gy,seat+c['geophone_height'],12,c['geophone_terminal_headroom']),
      'geophone_header':box(7.78,49.7,hat_top,20.6,58.9,hat_top+7.25),
      'geophone_plug':box(8.08,58.9,hat_top,20.3,75,hat_top+11.1),
      'pi_heatsink':box(22,19,pi_top,40,37,pi_top+13.3),
      'fpga_heatsink':box(44,18,hat_top+12.16,70,40,hat_top+24.16),
      'gpio_stack':box(6.8,1.025,pi_top,58.2,5.975,hat_bottom),
      'j83':box(90.5,.2,hat_top,99.5,14.6,hat_top+11),
      'j130':box(113.39,3.5,hat_top,122.8,12.7,hat_top+7.25),
      'u132':box(121.5,25.25,hat_top,126.5,30.75,hat_top+4),
      'c135':cylinder(135,27,hat_top,3.3,7.7),
      'u80':box(92.5,29.25,hat_top,97.5,34.75,hat_top+4),
      'c89':cylinder(105,45,hat_top,3.3,7.7),
      'sw80':box(102,7,hat_top,108,13,hat_top+3.5),
      'infrasound':box(1.5,22.215,hat_top,10.65,37.025,hat_top+17.25),
      'pi_audio':box(49,47,pi_top,56,58,pi_top+6),
      'pi_sd':box(-2,20,pi_bottom-2.5,15,36,pi_bottom)}
    for name,(a,b,cc,d,e,f) in {
      'ethernet':(65.5,2.5,0,86.5,18.5,16),
      'usb1':(65.5,21.5,0,86.5,36.5,16),
      'usb2':(65.5,39.5,0,86.5,54.5,16),
      'power':(6.5,51,0,15.5,57,3.2),
      'hdmi1':(22.5,51,0,29.5,57,3),
      'hdmi2':(35.5,51,0,42.5,57,3)}.items():
        ref['pi_'+name]=box(a,b,pi_top+cc,d,e,pi_top+f)
    for i,(x,y) in enumerate(c['pi_holes']):
        ref['pi_spacer_'+str(i)]=cylinder(x,y,pi_top,2.4,c['pi_to_hat_gap'])
    for i,(x,y) in enumerate(c['trenz_holes']):
        ref['fpga_spacer_'+str(i)]=cylinder(x,y,hat_top,2.5,c['hat_to_fpga_gap'])
    ref={name:(solid if name in ('geophone','geophone_terminals') else stack_pose(c,solid))
         for name,solid in ref.items()}
    parts={'base':base,'cover':cover,'geophone-jaw':jaw,'cable-clamp':cap,'fit-coupon':coupon}
    levels=dict(pi_bottom=pi_bottom,pi_top=pi_top,hat_bottom=hat_bottom,hat_top=hat_top,
                fpga_bottom=fpga_bottom,fpga_top=fpga_top,roof_inside=roof,cable_z=cable_z)
    # The planar authoring coordinates are Y-down; the exported solids are Z-up.
    # This is a basis conversion for authored 2D geometry, not a reflection of
    # imported physical component models. Keep the manufacturer's chirality.
    parts={name:solid.mirror('XZ') for name,solid in parts.items()}
    ref={name:solid.mirror('XZ') for name,solid in ref.items()}
    return parts,ref,levels


def print_pose(name,solid,c):
    # Cover prints upside down with its exterior roof on the bed.
    if name=='cover':solid=solid.rotate((0,0,0),(1,0,0),180)
    bb=solid.val().BoundingBox()
    return solid.translate((-bb.xmin,-bb.ymin,-bb.zmin))


def export(c,out):
    out.mkdir(parents=True,exist_ok=True)
    reference=ROOT/'.local/case/reference';reference.mkdir(parents=True,exist_ok=True)
    for name in ('prints','cad','preview','evidence'):(out/name).mkdir(exist_ok=True)
    parts,ref,levels=build(c)
    assembly=cq.Assembly(name='Groundlark_case_'+c['revision'])
    colors={'base':(.10,.22,.28),'cover':(.14,.27,.32),'geophone-jaw':(.94,.51,.13),'cable-clamp':(.94,.51,.13)}
    for name,solid in parts.items():
        assert solid.val().isValid() and len(solid.solids().vals())==1,name
        pose=print_pose(name,solid,c)
        cq.exporters.export(pose,str(out/'prints'/(name+'.stl')),tolerance=.025,angularTolerance=.12)
        cq.exporters.export(pose,str(out/'cad'/(name+'.step')))
        cq.exporters.export(solid,str(reference/(name+'-assembled.stl')),tolerance=.035,angularTolerance=.15)
        if name!='fit-coupon':assembly.add(solid,name=name,color=cq.Color(*colors[name]))
    assembly.save(str(out/'cad/case-assembly.step'))
    for name,solid in ref.items():cq.exporters.export(solid,str(reference/('reference-'+name+'.stl')),tolerance=.05,angularTolerance=.2)
    (out/'evidence/levels.json').write_text(json.dumps(levels,indent=2)+'\n')
    print('Exported five printable parts and assembly STEP:',out)
    return parts,ref,levels


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'hw/releases/groundlark-case-r3')
    args=ap.parse_args();export(json.loads((HERE/'parameters.json').read_text()),args.output)
