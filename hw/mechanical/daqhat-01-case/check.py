"""Geometric/mesh checks, deliberately not physical or thermal qualification."""
from pathlib import Path
import hashlib,json,math,sys
import cadquery as cq
import trimesh
from case import HERE,ROOT,LOGO,build,box,cylinder
sys.path.insert(0,str(ROOT/'hw/tools'))
from project_paths import load_layout,placement_path,board_dir

OUT=ROOT/'hw/releases/groundlark-case-r3'


def common(a,b):
    return a.val().intersect(b.val()).Volume()


def validate(c,parts,refs,levels):
    # Independent Pi 4 mounting fixture and native HAT placement metadata.
    fixture={(3.5,3.5),(61.5,3.5),(3.5,52.5),(61.5,52.5)}
    assert set(map(tuple,c['pi_holes']))==fixture,'Pi mounting pattern'
    layout=load_layout('groundlark-daqhat-01')['groundlark-daqhat-01']
    placements={p['ref']:p['xy'] for p in layout['parts']}
    assert {tuple(placements[r]) for r in ('H1','H2','H3','H4')}==fixture,'HAT mounting pattern'
    assert set(map(tuple,c['trenz_holes']))=={tuple(placements[r]) for r in ('H80','H81','H82','H83')},'Trenz supports'
    assert abs(levels['hat_bottom']-levels['pi_top']-28.06)<1e-6,'GPIO riser height'
    assert abs(levels['fpga_bottom']-levels['hat_top']-8)<1e-6,'Trenz stack height'
    assert c['geophone_diameter']==25.4 and c['geophone_height']==33,'Racotech nominal body'
    assert c['geophone_diametral_clearance']>=.15,'Geophone tolerance allowance'
    assert c['geophone_terminal_headroom']>=10,'Terminal headroom'
    assert c['wall']>=2.8 and c['floor']>=5,'Case wall/floor thickness'
    assert c['stack_rotation_deg']==180,'Stack orientation'
    assert c['hat_size']==layout['size']==[140,56],'Current HAT outline'
    power={p['ref']:p for p in layout['parts']}
    assert power['J83']['xy']==[95,14.1] and power['J83']['angle']==180,'Power jack native pose'
    assert power['SW80']['xy']==[105,10],'Switch native pose'
    bb=refs['hat'].val().BoundingBox()
    assert abs(bb.xmin+55)<1e-5 and abs(bb.xmax-85)<1e-5,'HAT extension missing'
    jack=refs['j83'].val().BoundingBox()
    assert abs(jack.xmin+14.5)<.001 and abs(jack.ymin+55.8)<.001,'FPGA jack handedness'
    assert refs['geophone_plug'].val().BoundingBox().ymin>0 and jack.ymax<0,'Opposite power/geophone exits'
    # Independent power-wing underside bearing probes, in physical assembly XY.
    for yy in (-53.5,-2.5):
        bearing=box(-24.8,yy-1.3,levels['hat_bottom']-.2,-22.2,yy+1.3,levels['hat_bottom'])
        assert common(parts['base'],bearing)>bearing.val().Volume()*.999,'Power wing support missing'
    for ya,yb in ((-59.1,-56.5),(.5,3.1)):
        stop=box(-21.8,ya,levels['hat_bottom'],-19.2,yb,levels['hat_top']+.3)
        assert common(parts['base'],stop)>stop.val().Volume()*.999,'Power wing end stop missing'
    plug=box(-17,-90,levels['hat_top']-.5,-3,-55.8,levels['hat_top']+13.5)
    for name in ('base','cover','geophone-jaw','cable-clamp'):
        assert common(parts[name],plug)<1e-5,'FPGA plug access blocked'
    assert power['J130']['xy']==[120,10] and power['J130']['angle']==180,'Battery connector pose'
    assert power['J140']['xy']==[4,15.8] and power['J140']['angle']==0,'GNSS SMA pose'
    sma=refs['gnss_sma'].val().BoundingBox()
    assert abs(sma.xmax-92.5)<.001 and abs((sma.ymin+sma.ymax)/2+40.2)<.001,'GNSS SMA handedness'
    antenna_plug=box(88,-45.2,levels['hat_top']+.85,112,-35.2,levels['hat_top']+11.85)
    for name in ('base','cover','geophone-jaw','cable-clamp'):
        assert common(parts[name],antenna_plug)<1e-5,'GNSS SMA plug access blocked'
    battery_plug=box(-38.5,-90,levels['hat_top']-.5,-25.5,-52.5,levels['hat_top']+12)
    for name in ('base','cover','geophone-jaw','cable-clamp'):
        assert common(parts[name],battery_plug)<1e-5,'Battery plug access blocked'
    for yy in (-53.5,-2.5):
        bearing=box(-54.8,yy-1.3,levels['hat_bottom']-.2,-52.2,yy+1.3,levels['hat_bottom'])
        assert common(parts['base'],bearing)>bearing.val().Volume()*.999,'Supervisor wing support missing'
    switch=box(-24,-50,levels['hat_top']+3.6,-16,-42,80)
    assert common(parts['cover'],switch)<1e-5,'FPGA switch access blocked'
    # Independent enclosure-space fixture: do not reuse the placement transform.
    mounts={(3.5,-3.5),(61.5,-3.5),(3.5,-52.5),(61.5,-52.5)} if c['stack_rotation_deg']==0 else {(81.5,-52.5),(23.5,-52.5),(81.5,-3.5),(23.5,-3.5)}
    for x,y in mounts:
        bore=cylinder(x,y,0,1.1,levels['pi_bottom'])
        assert common(parts['base'],bore)<1e-5,'Stack mounting bore blocked'
        bearing=cylinder(x,y,levels['pi_bottom']-.2,2.8,.2).cut(cylinder(x,y,levels['pi_bottom']-.3,1.5,.4))
        assert common(parts['base'],bearing)>bearing.val().Volume()*.999,'Stack mounting support missing'
    if c['stack_rotation_deg']==180:
        connector=refs['geophone_plug'].val().BoundingBox()
        assert connector.ymin>0 and connector.xmin>64,'Geophone connector must face the geophone bay'
        # Full conservative plug translated 12 mm out; cap/cable release precedes unplugging.
        corridor=box(64.7,2.9,levels['hat_top'],76.92,31,levels['hat_top']+11.1)
        for name in ('base','cover','geophone-jaw','cable-clamp'):
            assert common(parts[name],corridor)<1e-5,'J90 horizontal withdrawal blocked'
    # Independent physical landmarks from Raspberry Pi's top-view drawing.
    # With USB on physical -X after rotation, GPIO is on -Y and USB-C on +Y.
    expected={'pi_power':(74,-2,13.2),'gpio_stack':(52.5,-52.5,(levels['pi_top']+levels['hat_bottom'])/2)} if c['stack_rotation_deg']==180 else {'pi_power':(11,-54,13.2),'gpio_stack':(32.5,-3.5,(levels['pi_top']+levels['hat_bottom'])/2)}
    for name,xyz in expected.items():
        bb=refs[name].val().BoundingBox()
        center=((bb.xmin+bb.xmax)/2,(bb.ymin+bb.ymax)/2,(bb.zmin+bb.zmax)/2)
        assert max(abs(a-b) for a,b in zip(center,xyz))<.02, f'Pi physical handedness: {name}'
    gx,gy=c['geophone_center'];gy=-gy;seat=c['geophone_seat_z']
    seat_probe=cylinder(gx,gy,seat-.15,11,.15)
    assert common(parts['base'],seat_probe)>=seat_probe.val().Volume()*.999,'Geophone bearing seat missing'
    assert common(parts['geophone-jaw'].translate((-8,0,0)),parts['base'])<1e-5,'Jaw withdrawal blocked'
    for dz in (5,30,60):
        lifted=refs['geophone'].translate((0,0,dz))
        assert common(parts['base'],lifted)<1e-5,'Geophone vertical removal blocked'
    printable=['base','cover','geophone-jaw','cable-clamp']
    for name in printable:
        shape=parts[name]
        assert shape.val().isValid(),f'Invalid BRep: {name}'
        assert len(shape.solids().vals())==1,f'Disconnected printable part: {name}'
    overlaps=[]
    for i,a in enumerate(printable):
        for b in printable[i+1:]:
            v=common(parts[a],parts[b])
            assert v<1e-5, f'Printed parts overlap: {a}/{b}: {v}'
    for a in printable:
        for b,shape in refs.items():
            v=common(parts[a],shape)
            assert v<1e-5, f'Component collision: {a}/{b}: {v}'
            overlaps.append(dict(case_part=a,component=b,intersection_mm3=round(v,8)))
    # Port service rays extend beyond the body; blocked windows must fail.
    service={
       'USB/Ethernet plugs':box(86.5,-56,levels['pi_top'],98,-1,levels['pi_top']+17),
       'USB-C/HDMI/audio plugs':box(4,-69,levels['pi_top'],62,-57,levels['pi_top']+10),
       'microSD removal':box(-12,-36,7.5,0,-20,11),
    }
    if c['stack_rotation_deg']==180:
        service={
           'USB/Ethernet plugs':box(-70,-55,levels['pi_top'],-1.5,0,levels['pi_top']+17),
           'USB-C/HDMI/audio cable exit':box(23,1,levels['pi_top'],81,55,levels['pi_top']+10),
           'microSD removal':box(85,-36,7.5,98,-20,11),
        }
    for name,shape in service.items():
        for part in (('base','cover','geophone-jaw','cable-clamp') if name=='USB/Ethernet plugs' else ('cover',)):
            assert common(parts[part],shape)<1e-5,f'Blocked service access: {name}/{part}'
    if c['stack_rotation_deg']==180:
        # Explicit USB-C insertion sweep and cable route, including the base,
        # geophone and clamp. A 14 x 30 x 10 mm overmould leaves 1 mm to the
        # narrow side of the front exit; this is a limit, not a cable approval.
        sweep=box(67,1.01,8.2,81,65,18.2)
        for name,solid in {**{k:v for k,v in parts.items() if k!='fit-coupon'},
                           **{k:v for k,v in refs.items() if k!='pi_power'}}.items():
            assert common(solid,sweep)<1e-5,f'USB-C insertion blocked: {name}'
    # Cover removal is straight upward; no electronics need disconnecting first.
    for dz in (1,5,20,50):
        lifted=parts['cover'].translate((0,0,dz))
        assert common(lifted,plug)<1e-5,'Cover extraction blocked by DC plug'
        assert common(lifted,antenna_plug)<1e-5,'Cover extraction blocked by antenna plug'
        assert common(lifted,battery_plug)<1e-5,'Cover extraction blocked by battery plug'
        for name,shape in refs.items():
            assert common(lifted,shape)<1e-5,f'Cover extraction collision: {name}'
    return dict(component_intersections_checked=len(overlaps),
                collisions=0,service_windows=list(service)+['FPGA DC plug opposite geophone','FPGA switch roof access','Pi battery plug','GNSS SMA antenna'],gnss_plug_max_diameter_mm=10,fpga_plug_max_diameter_mm=14,power_wing_supports=4,board_mm=[140,56],case_outer_mm=[159,118,75],
                levels_mm=levels,geophone_body_clearance_diameter_mm=c['geophone_diametral_clearance'],
                geophone_terminal_clearance_to_roof_mm=c['roof_z']-c['geophone_seat_z']-c['geophone_height']-c['geophone_terminal_headroom'],
                fpga_heatsink_to_roof_mm=c['roof_z']-levels['hat_top']-24.16,
                stack_rotation_deg=c['stack_rotation_deg'],
                physical_basis='Right-handed Z-up; native board (x,y) maps to (x,-y) before physical rotation',
                pi_usb_c_overmould_envelope_mm=[14,30,10],
                cable_routing=('Pi power/HDMI/audio face the geophone bay; lid-off connection and routed leads required. Cable/plug fit remains unqualified.'
                               if c['stack_rotation_deg']==180 else 'Direct Pi port service windows'),
                scope='CAD envelopes and mesh validity only; not first-print fit, thermal, stiffness, or noise qualification')


def main():
    c=json.loads((HERE/'parameters.json').read_text());parts,refs,levels=build(c)
    report=validate(c,parts,refs,levels)
    meshes={}
    for name in parts:
        path=OUT/'prints'/(name+'.stl');m=trimesh.load_mesh(path)
        assert m.is_watertight and m.is_winding_consistent and m.volume>0,name
        assert len(m.split(only_watertight=False))==1,name
        assert abs(m.bounds[0][2])<1e-4,f'Not on print bed: {name}'
        assert all(m.extents[:2]<=220),f'Exceeds 220 mm print bed: {name}'
        meshes[name]=dict(watertight=True,connected_solids=1,print_bounds_mm=m.extents.tolist(),
                          volume_cm3=m.volume/1000,triangles=len(m.faces),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report['meshes']=meshes
    report['sources_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [HERE/'parameters.json',HERE/'case.py',HERE/'check.py',LOGO,placement_path('groundlark-daqhat-01'),
                  board_dir('groundlark-daqhat-01')/'groundlark-daqhat-01.kicad_pcb',
                  ROOT/'hw/tools/assembly_fit.py']}
    (OUT/'evidence/fit-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
