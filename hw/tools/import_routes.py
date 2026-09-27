"""Import this project's restricted Freerouting SES format, then fill GND planes.

KiCad's SES importer is not exposed by the CLI. This small importer accepts only the
through-via/straight-track format and native HDI snapshot used here, checks placement, and fails closed
on unknown route objects. Run check_design.py afterwards: import is not signoff.
"""
from pathlib import Path
from project_paths import board_dir
import sys,re,json
from kicad_support import save_board
import pcbnew as p
import sexpdata as sx

ROOT=Path(__file__).resolve().parents[2]
REMOVED_HAT_REFS={'U30','C30','C31','R30','R31','R32','R33','R34','R35','J3','F1','C50','D1','D2','TP3'}
REMOVED_HAT_NETS={'REMOTE_3V3','D_SCL_N','D_SCL_P','D_SDA_N','D_SDA_P'}
def children(n,key): return [x for x in n if isinstance(x,list) and x and str(x[0])==key]
def child(n,key): return next(iter(children(n,key)))
def vec(x,y): return p.VECTOR2I(round(x),round(y))

def main(name):
    folder=board_dir(name); path=folder/(name+'.kicad_pcb')
    b=p.LoadBoard(str(path)); s=sx.load(open(folder/(name+'.ses')))
    native_snapshot=str(s[1]).endswith('.native-full')
    routes=child(s,'routes'); res=child(routes,'resolution')
    assert str(res[1])=='um'; factor=1000/float(res[2])
    fps={f.GetReference():f for f in b.GetFootprints()}
    for c in children(child(s,'placement'),'component'):
        for pl in children(c,'place'):
            if name=='groundlark-hat' and str(pl[1]) in REMOVED_HAT_REFS:continue
            fp=fps[str(pl[1])]; xy=fp.GetPosition()
            assert abs(xy.x-float(pl[2])*factor)<101 and abs(xy.y+float(pl[3])*factor)<101, pl
            assert str(pl[4])==('back' if fp.IsFlipped() else 'front'),pl
            assert abs((fp.GetOrientationDegrees()-float(pl[5])+180)%360-180)<.001,pl
    meta=json.loads((folder/'electrical.json').read_text())
    grounds=meta.get('ground_layers',['In1.Cu',f'In{b.GetCopperLayerCount()-2}.Cu'])
    layers={'F.Cu':p.F_Cu,'B.Cu':p.B_Cu}
    layers.update({f'In{i}.Cu':getattr(p,f'In{i}_Cu') for i in range(1,b.GetCopperLayerCount()-1) if f'In{i}.Cu' not in grounds})
    nets=b.GetNetsByName()
    for track in list(b.GetTracks()):
        if native_snapshot or not track.IsLocked(): b.Delete(track)
    # Re-running replaces pours but preserves design-rule keepouts.
    for i in range(b.GetAreaCount()-1,-1,-1):
        zone=b.GetArea(i)
        if not zone.GetIsRuleArea(): b.Delete(zone)
    for net in children(child(routes,'network_out'),'net'):
        if name=='groundlark-hat' and str(net[1]) in REMOVED_HAT_NETS:continue
        ni=nets[str(net[1])]
        for obj in net[2:]:
            typ=str(obj[0])
            if typ=='wire':
                pathdata=child(obj,'path');layer=layers[str(pathdata[1])]
                width=round(float(pathdata[2])*factor);coords=pathdata[3:]
                points=[vec(float(coords[i])*factor,-float(coords[i+1])*factor) for i in range(0,len(coords),2)]
                for start,end in zip(points,points[1:]):
                    if start==end: continue
                    t=p.PCB_TRACK(b);t.SetStart(start);t.SetEnd(end);t.SetWidth(width);t.SetLayer(layer);t.SetNet(ni);t.SetLocked(native_snapshot and any(str(c[1])=='protect' for c in children(obj,'type')));b.Add(t)
            elif typ=='via':
                m=re.fullmatch(r'(MicroVia|Via)\[(\d+)-(\d+)\]_(\d+):(\d+)_um',str(obj[1]));assert m,obj
                micro=m[1]=='MicroVia';a,z,diameter,drill=map(int,m.groups()[1:])
                order=[p.F_Cu,*[b.GetLayerID(f'In{i}.Cu') for i in range(1,b.GetCopperLayerCount()-1)],p.B_Cu]
                if micro:
                    assert native_snapshot and meta.get('hdi') and (a,z) in [(0,1),(len(order)-2,len(order)-1)] and (diameter,drill)==(300,100),obj
                else:assert (a,z)==(0,len(order)-1) and (diameter,drill) in [(600,300),(450,200),(450,300)],obj
                if meta.get('fabrication',{}).get('process')=='standard-six-layer-through-via':
                    assert not micro and drill>=300 and diameter-drill>=150,obj
                v=p.PCB_VIA(b);v.SetPosition(vec(float(obj[2])*factor,-float(obj[3])*factor));v.SetWidth(diameter*1000);v.SetDrill(drill*1000);v.SetViaType(p.VIATYPE_MICROVIA if micro else p.VIATYPE_THROUGH);v.SetLayerPair(order[a],order[z]);v.SetNet(ni)
                if native_snapshot:
                    v.SetFrontTentingMode(p.TENTING_MODE_TENTED);v.SetBackTentingMode(p.TENTING_MODE_TENTED)
                    v.SetLocked(any(str(c[1])=='protect' for c in children(obj,'type')))
                b.Add(v)
            else: raise ValueError(obj)
    size=json.loads((folder/'electrical.json').read_text())['size_mm']
    for layer in [b.GetLayerID(name) for name in grounds]:
        z=p.ZONE(b);z.SetLayer(layer);z.SetNet(nets['GND']);z.SetLocalClearance(p.FromMM(.2));z.SetMinThickness(p.FromMM(.2));z.SetThermalReliefGap(p.FromMM(.25));z.SetThermalReliefSpokeWidth(p.FromMM(.3));z.Outline().NewOutline()
        for x,y in [(50.4,50.4),(49.6+size[0],50.4),(49.6+size[0],49.6+size[1]),(50.4,49.6+size[1])]: z.Outline().Append(vec(p.FromMM(x),p.FromMM(y)))
        b.Add(z)
    b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());save_board(str(path),b)
    print(name,len(b.GetTracks()),'tracks/vias; inner GND planes filled')

if __name__=='__main__':
    for name in sys.argv[1:] or ['groundlark-hat','groundlark-field-head']: main(name)
