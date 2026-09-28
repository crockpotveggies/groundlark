"""Check the detailed Pi CAD against independent landmarks and printed solids."""
import gzip
import hashlib
import json
from pathlib import Path

import cadquery as cq
from case import ROOT,HERE,build


def main():
    directory=ROOT/'hw/shared/models/raspberrypi4'
    raw=gzip.decompress((directory/'raspberry-pi-4b.step.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest()==json.loads((directory/'provenance.json').read_text())['sha256']
    path=ROOT/'.local/case/raspberry-pi-4b.step';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    source=cq.importers.importStep(str(path)).solids().vals()
    assert len(source)==89
    physical=[s.rotate((0,0,0),(1,0,0),90).translate((0,-56,0)) for s in source]
    # Official Pi 4 mechanical drawing: USB-C on the edge opposite GPIO.
    # These model indices belong to the pinned, hash-checked source above.
    power=physical[37].BoundingBox()
    assert abs((power.xmin+power.xmax)/2-11.2)<.01 and power.ymin<-56,'USB-C location/handedness'
    pcb=physical[0].BoundingBox()
    assert abs(pcb.xlen-85)<.01 and abs(pcb.ylen-56)<.01,'Pi board outline'
    for pin_pair in physical[10:30]:
        header=pin_pair.BoundingBox()
        assert abs((header.ymin+header.ymax)/2+3.5)<.2,'GPIO must be opposite USB-C'
    config=json.loads((HERE/'parameters.json').read_text());parts,refs,levels=build(config)
    # The community PCB includes 0.2 mm extra thickness. Seat its underside
    # on the supports and retain that conservative thickness in the fit check.
    placed=[s.translate((0,0,levels['pi_bottom']-pcb.zmin)).rotate((42.5,-28,0),(42.5,-28,1),config['stack_rotation_deg']) for s in physical]
    collisions=[];checked=0
    for name,part in parts.items():
        if name=='fit-coupon':continue
        a=part.val();ab=a.BoundingBox()
        for i,b in enumerate(placed):
            bb=b.BoundingBox();checked+=1
            if any(getattr(ab,axis+'max')<=getattr(bb,axis+'min') or getattr(bb,axis+'max')<=getattr(ab,axis+'min') for axis in 'xyz'):continue
            volume=a.intersect(b).Volume()
            if volume>1e-4:collisions.append(dict(case_part=name,pi_solid=i,intersection_mm3=volume))
    report=dict(components=len(source),component_intersections_checked=checked,collisions=collisions,
                source_sha256=hashlib.sha256(raw).hexdigest(),model_pcb_thickness_mm=pcb.zlen,
                placement='Model underside seated on Pi supports; community CAD retains 1.8 mm PCB thickness versus nominal 1.6 mm.',
                check_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                scope='Detailed community Pi CAD versus printed parts; independent official outline and USB-C landmark. Physical fit remains pending.')
    out=ROOT/'hw/releases/groundlark-case-r2/evidence/detailed-pi-fit.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    assert not collisions,'Detailed Pi CAD collides with printed enclosure'


if __name__=='__main__':main()
