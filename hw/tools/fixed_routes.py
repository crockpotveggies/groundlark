"""Apply reviewed fixed copper geometry; nets must already exist in atopile's board."""
from pathlib import Path
import json
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
def point(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def add(b):
    for row in json.loads((ROOT/'hw/groundlark-coldfoot-hat/layout/fixed-routes.json').read_text()):
        if row['type']=='via':
            t=p.PCB_VIA(b);t.SetPosition(point(row['at']));t.SetWidth(p.FromMM(row['width']));t.SetDrill(p.FromMM(row['drill']));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu)
        else:
            t=p.PCB_TRACK(b);t.SetStart(point(row['start']));t.SetEnd(point(row['end']));t.SetWidth(p.FromMM(row['width']));t.SetLayer(b.GetLayerID(row['layer']))
        t.SetNet(b.GetNetsByName()[row['net']]);t.SetLocked(True);b.Add(t)
if __name__=='__main__':
    # Export only already-authored, locked connector fanout. GNSS RF is held
    # separately by assemble_pcb.py. This does not invent electrical nets.
    b=p.LoadBoard(str(ROOT/'hw/groundlark-coldfoot-hat/boards/groundlark-hat/groundlark-hat.kicad_pcb'));rows=[]
    for t in b.GetTracks():
        if not t.IsLocked() or t.GetNetname()=='GNSS_RF':continue
        row={'net':t.GetNetname()}
        if t.GetClass()=='PCB_VIA':row.update(type='via',at=[p.ToMM(v) for v in t.GetPosition()],width=p.ToMM(t.GetWidth(p.F_Cu)),drill=p.ToMM(t.GetDrillValue()))
        else:row.update(type='track',start=[p.ToMM(v) for v in t.GetStart()],end=[p.ToMM(v) for v in t.GetEnd()],width=p.ToMM(t.GetWidth()),layer=b.GetLayerName(t.GetLayer()))
        rows.append(row)
    (ROOT/'hw/groundlark-coldfoot-hat/layout/fixed-routes.json').write_text(json.dumps(rows,indent=2));print('Stored',len(rows),'fixed connector routing objects')
