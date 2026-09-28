"""Geometric/mesh checks, deliberately not physical or thermal qualification."""
from pathlib import Path
import hashlib,json,math,sys
import cadquery as cq
import trimesh
from case import HERE,ROOT,LOGO,build,box,cylinder
sys.path.insert(0,str(ROOT/'hw/tools'))
from project_paths import load_layout,placement_path,board_dir

OUT=ROOT/'hw/releases/groundlark-case-r1'


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
    assert c['stack_rotation_deg'] in (0,180),'Stack orientation'
    # Independent enclosure-space fixture: do not reuse the placement transform.
    mounts=fixture if c['stack_rotation_deg']==0 else {(81.5,52.5),(23.5,52.5),(81.5,3.5),(23.5,3.5)}
    for x,y in mounts:
        bore=cylinder(x,y,0,1.1,levels['pi_bottom'])
        assert common(parts['base'],bore)<1e-5,'Stack mounting bore blocked'
        bearing=cylinder(x,y,levels['pi_bottom']-.2,2.8,.2).cut(cylinder(x,y,levels['pi_bottom']-.3,1.5,.4))
        assert common(parts['base'],bearing)>bearing.val().Volume()*.999,'Stack mounting support missing'
    if c['stack_rotation_deg']==180:
        connector=refs['geophone_plug'].val().BoundingBox()
        assert connector.ymax<0 and connector.xmin>64,'Geophone connector must face the geophone bay'
        # Full conservative plug translated 12 mm out; cap/cable release precedes unplugging.
        corridor=box(64.7,-31,levels['hat_top'],76.92,-2.9,levels['hat_top']+11.1)
        for name in ('base','cover','geophone-jaw','cable-clamp'):
            assert common(parts[name],corridor)<1e-5,'J90 horizontal withdrawal blocked'
    gx,gy=c['geophone_center'];seat=c['geophone_seat_z']
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
       'USB/Ethernet plugs':box(86.5,1,levels['pi_top'],98,56,levels['pi_top']+17),
       'USB-C/HDMI/audio plugs':box(4,57,levels['pi_top'],62,69,levels['pi_top']+10),
       'microSD removal':box(-12,20,7.5,0,36,11),
    }
    if c['stack_rotation_deg']==180:
        service={
           'USB/Ethernet plugs':box(-13,0,levels['pi_top'],-1.5,55,levels['pi_top']+17),
           'USB-C/HDMI/audio cable exit':box(23,-55,levels['pi_top'],81,-1,levels['pi_top']+10),
           'microSD removal':box(85,20,7.5,98,36,11),
        }
    for name,shape in service.items():
        assert common(parts['cover'],shape)<1e-5,f'Blocked service access: {name}'
    # Cover removal is straight upward; no electronics need disconnecting first.
    for dz in (1,5,20,50):
        lifted=parts['cover'].translate((0,0,dz))
        for name,shape in refs.items():
            assert common(lifted,shape)<1e-5,f'Cover extraction collision: {name}'
    return dict(component_intersections_checked=len(overlaps),
                collisions=0,service_windows=list(service),
                levels_mm=levels,geophone_body_clearance_diameter_mm=c['geophone_diametral_clearance'],
                geophone_terminal_clearance_to_roof_mm=c['roof_z']-c['geophone_seat_z']-c['geophone_height']-c['geophone_terminal_headroom'],
                fpga_heatsink_to_roof_mm=c['roof_z']-levels['hat_top']-24.16,
                stack_rotation_deg=c['stack_rotation_deg'],
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
