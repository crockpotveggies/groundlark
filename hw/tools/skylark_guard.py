"""Guard pours for the high-impedance cell region, driven through R75.

Only authoring/import commands call add_zones. Read-only checks inspect the
resulting filled copper. Cleanliness and humid leakage still require measurement.
"""
import pcbnew as p
from kicad_support import v

def add_zones(board):
    for layer,ymax in [(p.F_Cu,47),(p.B_Cu,44.5)]:
        z=p.ZONE(board);z.SetLayer(layer);z.SetNet(board.FindNet('GUARD'))
        z.SetLocalClearance(p.FromMM(.3));z.SetMinThickness(p.FromMM(.2))
        z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.Outline().NewOutline()
        for x,y in [(7,15),(83,15),(83,ymax),(7,ymax)]:z.Outline().Append(v(50+x,50+y))
        board.Add(z)

def expose_socket_guards(board):
    """Open mask only where filled guard copper surrounds each WE/RE/AE pad.

    Gaps at signal crossings retain mask. These openings must be cleaned and
    coated using a qualified low-leakage process before cells are installed.
    """
    import math
    for item in list(board.GetDrawings()):
        if item.GetLayer()==p.F_Mask:board.Delete(item)
    filled=[z.GetFilledPolysList(p.F_Cu) for z in board.Zones() if z.GetNetname()=='GUARD' and not z.GetIsRuleArea() and z.IsOnLayer(p.F_Cu)]
    counts={}
    for fp in board.GetFootprints():
        if fp.GetReference() not in ('GS1','GS2'):continue
        for pad in fp.Pads():
            if pad.GetNumber() not in ('WE','RE','AE'):continue
            center=pad.GetPosition();count=0
            for i in range(48):
                angles=[2*math.pi*(i+offset)/48 for offset in (0,.5,1)]
                probes=[v(p.ToMM(center.x)+rad*math.cos(a),p.ToMM(center.y)+rad*math.sin(a)) for rad in (2.45,2.6,2.75) for a in angles]
                if not all(any(poly.Contains(q) for poly in filled) for q in probes):continue
                a,z=[v(p.ToMM(center.x)+2.6*math.cos(t),p.ToMM(center.y)+2.6*math.sin(t)) for t in (angles[0],angles[-1])]
                shape=p.PCB_SHAPE(board);shape.SetShape(p.SHAPE_T_SEGMENT);shape.SetStart(a);shape.SetEnd(z);shape.SetWidth(p.FromMM(.2));shape.SetLayer(p.F_Mask);board.Add(shape);count+=1
            counts[fp.GetReference()+'.'+pad.GetNumber()]=count/48
    return counts

if __name__=='__main__':
    from project_paths import board_dir
    from kicad_support import save_board
    path=board_dir('skylark-usb')/'skylark-usb.kicad_pcb';b=p.LoadBoard(str(path))
    for z in list(b.Zones()):
        if not z.GetIsRuleArea() and z.GetNetname()=='GUARD':b.Delete(z)
    add_zones(b);p.ZONE_FILLER(b).Fill(b.Zones());print(expose_socket_guards(b));save_board(str(path),b)
