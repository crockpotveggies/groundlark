"""Skylark Three.js view: native PCB, authored package geometry and pick targets."""
import json
import math
from pathlib import Path


def add_skylark(scene, targets, rings, color):
    root=Path(__file__).resolve().parents[2]
    parts=json.loads((root/'hw/skylark-usb/layout/placement.json').read_text())['skylark-usb']['parts']
    positions={p['ref']:p['xy'] for p in parts}
    with scene.group() as board:
        scene.gltf('/board-assets/skylark.glb').scale(100).rotate(math.pi/2,0,0).move(-9.5,10,0)
        for ref, sid, label, radius, z in [('GS1',10,'SO₂',1.58,2.26),('GS2',12,'H₂S',1.58,2.26),
                                           ('U11',15,'SHT40',.3,.32),('U12',16,'BMP390',.3,.34)]:
            x,y=positions[ref];x,y=(x-45)/10,(50-y)/10
            ring=scene.ring(radius,radius+.06,64).move(x,y,z).material(color)
            targets[ring.id]=sid;rings[sid]=[ring]
            if sid in (10,12): rings[sid+1]=[ring]
            pick=scene.cylinder(radius,radius,.05).rotate(math.pi/2,0,0).move(x,y,z-.04).material(color,.12)
            targets[pick.id]=sid
            scene.text(label,'color:white;font-size:12px;pointer-events:none').move(x,y,z+.25)
        # Nominal 50 x 38 x 21 mm PMS5003, displayed beside the PCB. This is
        # an exploded inspection view, not the bell assembly's mounted pose.
        pm=scene.box(3.8,5,2.1).move(7,0,1.21).material('#4f78a4')
        targets[pm.id]=14
        ring=scene.ring(2.5,2.56,64).move(7,0,2.3).material(color);targets[ring.id]=14;rings[14]=[ring]
        scene.text('PMS5003','color:white;font-size:12px;pointer-events:none').move(7,0,2.7)
        scene.text('SKYLARK USB / 90 × 100 mm','color:#a6bfcc;font-size:11px;pointer-events:none').move(0,-5.5,.1)
    board.visible(False)
    return board
