"""Dimensioned display geometry only; signal models stay in groundlark.stimulus.

Scene units are centimetres. Racotech nominal body: diameter 25.4 mm, height
33 mm. Terminals and flexible lead routing are illustrative, not vendor CAD.
"""
import math


def add_geophone(scene, connector_xy, targets, rings, accent):
    x,y,z=-6.0,0.0,.1
    radius,height=1.27,3.3
    for name,r,h,cz,color in (
        ('geophone-body',radius,height,z,'#ae9455'),
        ('geophone-cap',radius,.10,z+height/2,'#252b34'),
        ('geophone-base',radius+.025,.08,z-height/2,'#c4aa65'),
    ):
        body=scene.cylinder(r,r,h,48).rotate(math.pi/2,0,0).move(x,y,cz).material(color).with_name(name)
        targets[body.id]=9
    ring=scene.ring(radius+.06,radius+.14,64).move(x,y,z+height/2+.08).material(accent).with_name('geophone-selection')
    rings.setdefault(9,[]).append(ring);targets[ring.id]=9
    cx,cy=connector_xy
    # Caller supplies pin 1; 1803280 opens along board +Y (scene -Y).
    cy-=.8
    for dx,pin_offset,color in ((-.45,0,'#df655b'),(.45,.381,'#344656')):
        terminal_z=z+height/2+.18
        terminal=scene.cylinder(.06,.06,.35,16).rotate(math.pi/2,0,0).move(x+dx,y,terminal_z).material('#d2d6dc')
        targets[terminal.id]=9
        scene.quadratic_bezier_tube([x+dx,y,terminal_z+.17],[cx+pin_offset,cy-1,.52],
            [cx+pin_offset,cy,.52],radius=.04).material(color).with_name('geophone-lead')
    scene.text('RACOTECH GEOPHONE', 'color:#e8f5ff;font-size:11px;background:#172534dc;padding:2px 5px;border-radius:4px;pointer-events:none').move(x,y,2.3)
