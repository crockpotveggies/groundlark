"""Independent Gerber/Excellon inspection, including USB plated slots.

Run using pcbnew 9 and gerbonara 1.5.0. No CAD writes or zone refills.
"""
import argparse
import json
import math
from pathlib import Path
from skylark_package import BOARD, ROOT, sha, write_json


def match(expected, actual, tolerance=.00101):
    remaining=list(actual)
    for want in expected:
        index=next((i for i,got in enumerate(remaining) if len(want)==len(got) and
                    all(abs(a-b)<=tolerance for a,b in zip(want,got))),None)
        if index is None: raise ValueError(f'Missing or misplaced drill/edge: {want}')
        remaining.pop(index)
    if remaining: raise ValueError('Unexpected drill/edge geometry')


def segment(x1,y1,x2,y2,width):
    a,b=sorted(((x1,y1),(x2,y2)))
    return (*a,*b,width)


def inspect(out):
    import pcbnew as p
    from gerbonara import ExcellonFile, GerberFile
    from gerbonara.graphic_objects import Line, Flash
    from gerbonara.utils import MM
    manifest=json.loads((out/'manifest.json').read_text())
    for path,digest in manifest['source_sha256'].items():
        if sha(ROOT/path)!=digest: raise ValueError('Source changed since export: '+path)
    for path,digest in manifest['files_sha256'].items():
        if sha(out/path)!=digest: raise ValueError('Package changed since export: '+path)
    b=p.LoadBoard(str(BOARD)); wanted={'PTH':[],'NPTH':[]}
    for f in b.GetFootprints():
        for a in f.Pads():
            dx,dy=p.ToMM(a.GetDrillSize())
            if not dx: continue
            x,y=p.ToMM(a.GetPosition()); kind='NPTH' if a.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH'
            if abs(dx-dy)<1e-7: wanted[kind].append((x,-y,dx)); continue
            angle=math.radians(a.GetOrientationDegrees())
            vx,vy=((dx-dy)/2,0) if dx>dy else (0,(dy-dx)/2)
            # KiCad rotations are CCW in the X-right/Y-up frame.
            ux=math.cos(angle)*vx+math.sin(angle)*vy
            uy=-math.sin(angle)*vx+math.cos(angle)*vy
            wanted[kind].append(segment(x-ux,-y+uy,x+ux,-y-uy,min(dx,dy)))
    for via in b.GetTracks():
        if isinstance(via,p.PCB_VIA):
            x,y=p.ToMM(via.GetPosition());wanted['PTH'].append((x,-y,p.ToMM(via.GetDrillValue())))
    result={'parser':'gerbonara 1.5.0','drills':{},'layers':{}}
    plots=out/'gerbers'
    for kind,expected in wanted.items():
        parsed=ExcellonFile.open(plots/f'skylark-usb-{kind}.drl');actual=[]
        for o in parsed.objects:
            if o.unit!=MM: raise ValueError('Expected metric drills')
            if isinstance(o,Flash): actual.append((o.x,o.y,o.tool.diameter))
            elif isinstance(o,Line): actual.append(segment(o.x1,o.y1,o.x2,o.y2,o.aperture.diameter))
            else: raise ValueError('Unexpected drill command')
        match(expected,actual)
        result['drills'][kind]={'round':sum(len(a)==3 for a in actual),'slots':sum(len(a)==5 for a in actual)}
    expected=[]
    for edge in b.GetDrawings():
        if edge.GetLayer()!=p.Edge_Cuts: continue
        if edge.GetShape()!=p.SHAPE_T_SEGMENT: raise ValueError('New outline shape needs inspection support')
        x1,y1=p.ToMM(edge.GetStart());x2,y2=p.ToMM(edge.GetEnd())
        expected.append(segment(x1,-y1,x2,-y2,0))
    for file in sorted(plots.iterdir()):
        if file.suffix in ('.drl','.gbrjob'): continue
        layer=GerberFile.open(file)
        if not layer.objects: raise ValueError('Empty Gerber: '+file.name)
        result['layers'][file.name]={'objects':len(layer.objects),'bounds_mm':layer.bounding_box(unit=MM)}
        if file.suffix=='.gm1':
            if any(not isinstance(o,Line) or not o.polarity_dark or o.unit!=MM for o in layer.objects):
                raise ValueError('Unexpected outline primitive')
            match(expected,[segment(o.x1,o.y1,o.x2,o.y2,0) for o in layer.objects])
            result['outline_segments']=len(expected)
    if len(result['layers'])!=11: raise ValueError('Expected eleven manufacturing layers')
    write_json(out/'review/independent-check.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('package',type=Path)
    print(json.dumps(inspect(parser.parse_args().package),indent=2))
