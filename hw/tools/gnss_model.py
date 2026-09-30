"""Authored HenryTech HL-SMA-KWE-02 display STEP from its dimensioned drawing.

Run with CadQuery. This conservative envelope is not a supplier mating model.
Local -X is the antenna exit, Z=0 is the PCB top. Dimensions are millimetres.
"""
from pathlib import Path
import cadquery as cq


def build():
    def box(x, y, z, a, b, c):
        return cq.Workplane('XY').box(a-x, b-y, c-z, centered=False).translate((x,y,z))
    def tube(start, length, radius):
        return cq.Workplane('YZ').center(0,6.35).circle(radius).extrude(length).translate((start,0,0))
    body=box(-3,-3,0,3,3,9.5).union(tube(-11.5,8.5,3.0))
    # Nominal thread crests for display; no fabricated thread or fit claim.
    for n in range(7):body=body.union(tube(-10+n*.7,.3,3.175))
    body=body.cut(tube(-11.6,5.5,2.5))
    for x in (-2.55,2.55):
        for y in (-2.55,2.55):body=body.union(box(x-.45,y-.45,-3.5,x+.45,y+.45,0))
    dielectric=tube(-11.25,5.1,2.45).cut(tube(-11.4,5.4,.65))
    contact=tube(-11.15,5,.6).cut(tube(-11.3,4,.35))
    pin=cq.Workplane('XY').circle(.45).extrude(3.5).translate((0,0,-3.5))
    assembly=cq.Assembly(name='HL_SMA_KWE_02')
    assembly.add(body,name='gold_body',color=cq.Color(.72,.52,.16))
    assembly.add(dielectric,name='PTFE',color=cq.Color(.94,.94,.90))
    assembly.add(contact.union(pin),name='socket_and_pin',color=cq.Color(.8,.61,.2))
    return assembly


if __name__=='__main__':
    models=Path(__file__).resolve().parents[1]/'shared/models'
    build().save(str(models/'HL_SMA_KWE_02.step'))
    # MAX-M10S nominal package envelope: 9.7 x 10.1 x 2.5 mm.
    # Shield detail is illustrative; use the u-blox package drawing for release.
    module=cq.Assembly(name='MAX_M10S_envelope')
    module.add(cq.Workplane('XY').box(9.7,10.1,.6,centered=(True,True,False)),
               name='substrate',color=cq.Color(.08,.22,.14))
    module.add(cq.Workplane('XY').box(8.7,9.1,1.9,centered=(True,True,False)).translate((0,0,.6)),
               name='shield',color=cq.Color(.68,.70,.72))
    for side in (-1,1):
        for index in range(9):
            module.add(cq.Workplane('XY').box(.7,.8,.62,centered=(True,True,False)).translate((side*4.5,(index-4)*1.1,0)),
                       name=f'contact_{side}_{index}',color=cq.Color(.74,.55,.2))
    module.save(str(models/'MAX_M10S_envelope.step'))
