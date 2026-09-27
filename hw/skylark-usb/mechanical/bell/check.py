"""Check B-rep intersections, exported meshes and actual PCB mounting references.

Runs read-only against electrical CAD; no print, weather or airflow claims.
"""
import itertools
import json
from pathlib import Path
import argparse
import cadquery as cq
import trimesh
from enclosure import build, PRODUCT, DEFAULT_OUT, digest, box, cy, cz

def volume(a,b):return sum(s.Volume() for s in a.intersect(b).solids().vals())

def validate_modular_assembly(parts,refs):
    obstacles=[s for n,s in parts.items() if n!='fit-coupon']+list(refs.values())
    bounds=[s.val().BoundingBox() for s in obstacles]
    for dz in (0,10,40,80):
        assert volume(parts['pcb-carrier'].translate((0,0,dz)),parts['gas-splash-cover'])<1e-4,'Carrier cannot lower over splash cover'
    def clear(probe,message):
        b=probe.val().BoundingBox()
        for obj,a in zip(obstacles,bounds):
            if (a.xmin<b.xmax and a.xmax>b.xmin and a.ymin<b.ymax and
                a.ymax>b.ymin and a.zmin<b.zmax and a.zmax>b.zmin):
                assert volume(obj,probe)<1e-4,message
    # Finished coordinates, actual screw lengths, and conservative M3 heads.
    for x,y in [(16,-34),(45,-34),(-28,32),(29,32)]:
        clear(cz(x,y,4,1.5,25),'New assembly screw obstructed')
        clear(cz(x,y,29,3,3),'New assembly screw head obstructed')
    for x,y in [(-43,-39),(-45,-6)]:
        clear(cz(x,y,2,1.5,10),'New assembly screw obstructed')
        clear(cz(x,y,12,3,3),'New assembly screw head obstructed')
    for x,y in [(-10,-39.5),(11,-15)]:
        clear(cz(x,y,-3,1.5,16),'New assembly screw obstructed')
        clear(cz(x,y,-6,3,3),'New assembly screw head obstructed')
    for x,y in [(-24,0),(4,0)]:
        clear(cz(x,y,-3,1.5,12),'New assembly screw obstructed')
        clear(cz(x,y,-6,3,3),'New assembly screw head obstructed')
    # Each eye needs a horizontal tunnel AND an open upward turn for the tie.
    for y0,y1,g0,g1 in [(-43,-36.1,-38.9,-36.1),(-8.9,-2,-8.9,-6.1)]:
        clear(box(-35.8,y0,10.1,-28.2,y1,12.9),'PMS tie path obstructed')
        clear(box(-35.8,g0,12.8,-28.2,g1,22.1),'PMS tie path obstructed')

def validate_bottom_ventilation(parts,refs):
    # Independent finished-coordinate fixtures. Areas describe geometry, not flow.
    slots=[(x,-27,x+6,1) for x in (16,24,32,40)]
    slots += [(23,-34,39,-29),(-28,18,-18,27),(20,18,30,27)]
    slots += [(x,18,x+10,33) for x in (-16,-4,8)]
    obstacles=[s for n,s in parts.items() if n!='fit-coupon']+list(refs.values())
    bounds=[s.val().BoundingBox() for s in obstacles]
    def clear(probe,message):
        b=probe.val().BoundingBox()
        for obj,a in zip(obstacles,bounds):
            if (a.xmin<b.xmax and a.xmax>b.xmin and a.ymin<b.ymax and
                a.ymax>b.ymin and a.zmin<b.zmax and a.zmax>b.zmin):
                assert volume(obj,probe)<1e-4,message
    for x0,y0,x1,y1 in slots:
        clear(box(x0,y0,-24,x1,y1,8.5),'Bottom gas aperture obstructed')
        cover=box(x0,y0,26.25,x1,y1,28.75)
        assert abs(volume(parts['gas-splash-cover'],cover)-cover.val().Volume())<1e-3,'Gas splash cover missing'
    # Clear exit curtains exceed each bank's floor aperture area. Count only
    # these unobstructed sides; ignore the narrower wall-side gaps entirely.
    exits=[(21,-39,9,40,-38,26),(49,-28,9,50,1,26),
           (11,-27,13,12,1,26),(-23,36,9,24,37,26)]
    for extents in exits:clear(box(*extents),'Gas baffle exit obstructed')
    # Connected risers and a cross-passage below the cell faces; rear riser is
    # alongside the mount pocket. These are clearance probes, not a flow model.
    for extents in [(10,-26,25,11,-20,85),(49,-28,25,50,-8,85),
                    (-25,-30,82,50,-24,85),(-23,36,25,-9,37,130)]:
        clear(box(*extents),'Gas chamber passage obstructed')
    return {'floor_open_area_mm2':sum((c-a)*(d-b) for a,b,c,d in slots),
            'banks_mm2':[752,630],'verified_baffle_exit_area_mm2':[1180,799],
            'scope':'Clear bottom apertures, covered slots, baffle exits and chamber passages; no flow-rate claim'}

def validate_sensor_packing(refs):
    pms=refs['pms5003']
    b=pms.val().BoundingBox()
    assert all(abs(a-e)<1e-5 for a,e in zip(
        (b.xlen,b.ylen,b.zlen),(50,21,38))),'PMS orientation must be parallel to PCB with ports down'
    for name,obj in refs.items():
        if name!='pms5003':
            assert volume(pms,obj)<1e-4,('PMS collides with electronics',name)

def validate_cell_stack(parts,refs):
    # Mill-Max 0322 drawing: 0.192 in = 4.8768 mm from seating plane
    # to upper rim. Its 0.032 in flange is included in that dimension.
    rear=parts['cell-retainer'].val().BoundingBox().ymax
    for name in ('so2','h2s'):
        b=refs[name].val().BoundingBox()
        assert abs(b.ymax+4.88)<.005 and abs(b.ylen-15.5)<.005,'Socket seating datum'
        assert abs(b.ymin-rear-.31)<.005,'Cell retainer withdrawal clearance'

def validate_air_paths(installed):
    # Independent occupied-volume probes: membrane opening and downward PM ducts.
    for x in (-21,21):
        probe=cy(x,-40,106,10.5,18.5)
        assert all(volume(p,probe)<1e-4 for p in installed.values()),'Gas membrane obstructed'
    for x0,x1 in [(-43,-23),(-19,3.5)]:
        probe=box(x0,-31.8,-26,x1,-13.2,21.3)
        assert all(volume(p,probe)<1e-4 for p in installed.values()),'PMS air path obstructed'

def validate_mount_and_service(parts):
    hood=parts['hood']
    assert abs(hood.val().BoundingBox().zmin+25)<1e-5,'Skirt must extend 25 mm below tray'
    assert hood.val().BoundingBox().ymax<47.0001,'Rear mount must remain flush'
    for z in (45,125):
        for dz in range(-10,1):
            screw=cy(0,39.6,z+dz,4,3.5).union(cy(0,43.1,z+dz,2,8))
            assert volume(hood,screw)<1e-4,'M4 sliding path obstructed'
        for dy in (0,2,4,6,8,10):
            head=cy(0,39.6+dy,z-10,4,3.5)
            assert volume(hood,head)<1e-4,'M4 head entry obstructed'
        # The seated head must overlap the retaining wall if pulled rearward.
        assert volume(hood,cy(0,44,z,4,2.5))>40,'Keyhole does not retain the head'
        shield=box(-3,37,z-10,3,39,z)
        assert abs(volume(hood,shield)-120)<1e-3,'Mount pocket opens into sensor chamber'
    for x in (-55,55):
        for y in (-35,35):
            tool=cz(x,y,-45,3.0,46)
            for name in ('hood','pms-exhaust-extension'):
                assert volume(parts[name],tool)<1e-4,'Bottom screw inaccessible'
    for name in ('bottom','pcb-carrier','cell-retainer','pms-cradle','gas-splash-cover','pms-exhaust-extension','cable-left','cable-right'):
        for dz in (-10,-30,-80,-150):
            assert volume(hood,parts[name].translate((0,0,dz)))<1e-4,('Tray removal collision',name,dz)

def check(out):
    parts,refs=build();findings=[]
    validate_cell_stack(parts,refs)
    provenance=json.loads((out/'provenance.json').read_text())
    assert provenance['pcb_sha256']==digest(PRODUCT/'boards/skylark-usb/skylark-usb.kicad_pcb')
    assert provenance['placement_sha256']==digest(PRODUCT/'layout/placement.json')
    assert provenance['source_sha256']==digest(Path(__file__).with_name('enclosure.py'))
    for name,sha in provenance['files'].items():assert digest(out/name)==sha,('Stale export',name)
    meshes={}
    for name,part in parts.items():
        mesh=trimesh.load(out/(name+'.stl'),force='mesh')
        meshes[name]={'watertight':bool(mesh.is_watertight),'bodies':int(mesh.body_count),
                      'extents_mm':mesh.extents.tolist(),'volume_mm3':float(mesh.volume)}
        if not mesh.is_watertight or mesh.body_count!=1 or mesh.volume<=0:findings.append(('mesh',name))
    actual={tuple(row['xy']) for row in json.loads((PRODUCT/'layout/placement.json').read_text())['skylark-usb']['parts'] if row['ref'].startswith('H') and row['type'] is None}
    assert actual=={(4,4),(86,4),(4,96),(86,55)},actual
    # Through-bore at each mounting point must remain clear through the carrier.
    for x,z in [(-41,131),(41,131),(-41,39),(41,80)]:
        assert volume(parts['pcb-carrier'],cy(x,1.5,z,1.5,15))<1e-5
    intersections=[]
    installed={k:v for k,v in parts.items() if k!='fit-coupon'}
    for (a,sa),(b,sb) in itertools.combinations(installed.items(),2):
        v=volume(sa,sb)
        if v>1e-4:findings.append(('printed-parts',a,b,v))
    for name,part in installed.items():
        for ref,obj in refs.items():
            # Mated USB plug necessarily overlaps the receptacle, but not plastic.
            v=volume(part,obj)
            if v>1e-4:intersections.append((name,ref,v))
    findings.extend(intersections)
    validate_air_paths(installed)
    validate_mount_and_service(installed)
    validate_sensor_packing(refs)
    ventilation=validate_bottom_ventilation(installed,refs)
    validate_modular_assembly(installed,refs)
    # Electronics tops have room to slide vertically into the open hood.
    for name,obj in refs.items():
        for dz in (-40,-80,-120):
            assert volume(parts['hood'],obj.translate((0,0,dz)))<1e-4,('Insertion collision',name,dz)
    result={'status':'pass' if not findings else 'fail','meshes':meshes,'intersections':findings,
            'bottom_gas_ventilation':ventilation,
            'modular_assembly':'Cover, cradle, shared exhaust and cable-clamp screw envelopes and tie paths passed',
            'pcb_mounting_holes':'four independently checked coordinates',
            'gas_face_clearance_mm':.31,'gas_front_wall_clearance_mm':22.61,
            'pms_side_clearance_mm':.4,'hood_locating_rim_clearance_per_side_mm':.6,
            'pms_packing':'broad face parallel to PCB; no intersections with other electronics envelopes',
            'skirt_depth_mm':25,'M4_keyhole_pitch_mm':80,'mount_drop_mm':10,
            'mount_checks':'head entry, slide, retaining overlap and closed pocket passed',
            'service_access':'6 mm driver envelope and sampled downward tray removal passed',
            'limitations':['No physical fit, insert pullout, weather, flow, temperature or gas-response tests',
                          'Reference electronics are dimension envelopes, not manufacturer solid models',
                          'Coarse insertion samples; verify real cable routing and screw-tool access during assembly']}
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    assert not findings,findings

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    check(parser.parse_args().out)
