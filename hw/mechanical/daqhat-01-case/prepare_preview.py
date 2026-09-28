"""Tessellate existing vendor STEP for render only; do not modify it."""
import cadquery as cq,json
from pathlib import Path
from case import ROOT
out=ROOT/'.local/case';src=ROOT/'hw/shared/models/trenz/STP-TE0712-03-No Variations.step'
levels=json.loads((ROOT/'hw/releases/groundlark-case-r1/evidence/levels.json').read_text())
s=cq.importers.importStep(str(src));groups={'pcb':[],'black':[],'metal':[]}
for solid in s.solids().vals():
 b=solid.BoundingBox()
 placed=cq.Workplane(obj=solid).mirror('XZ').translate((30,48,levels['hat_top']+9.6099917)).val()
 color='pcb' if b.xlen>45 and b.ylen>35 and b.zlen<2 else ('black' if b.zlen>1.3 or b.xlen*b.ylen>25 else 'metal')
 groups[color].append(placed)
items=[]
for color,bodies in groups.items():
 name='fpga-'+color
 cq.exporters.export(cq.Compound.makeCompound(bodies),str(out/(name+'.stl')),tolerance=.06,angularTolerance=.2)
 items.append(dict(name=name,color=color))
(out/'fpga-bodies.json').write_text(json.dumps(items));print('Grouped manufacturer geometry for preview')
