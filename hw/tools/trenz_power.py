"""Add carrier power distribution on compiled nets after SES import.

Solid front pads, broad back copper and parallel through vias avoid relying on
signal-width autorouter tracks for the module input supply. Current capability
still requires fabricated copper/thermal validation.
"""
from pathlib import Path
import json,subprocess
from kicad_support import save_board
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'hw/groundlark-fpga-hat/boards/groundlark-daqhat-01';PATH=F/'groundlark-daqhat-01.kicad_pcb'
b=p.LoadBoard(str(PATH));nets=b.GetNetsByName()
def v(x,y):return p.VECTOR2I(p.FromMM(x+50),p.FromMM(y+50))
def track(a,c,net,width):
    t=p.PCB_TRACK(b);t.SetStart(v(*a));t.SetEnd(v(*c));t.SetWidth(p.FromMM(width));t.SetLayer(p.F_Cu);t.SetNet(nets[net]);t.SetLocked(True);b.Add(t)
# Retain routed connectivity. Pours supplement it with a parallel current path.
for z in list(b.Zones()):
    if not z.GetIsRuleArea() and z.GetNetname()=='FPGA_VIN':b.Delete(z)
for layer,points in [
 (p.F_Cu,[(17.2,7),(24,7),(24,10),(17.2,10)]),
 (p.F_Cu,[(41.8,8.5),(45.6,8.5),(45.6,10.8),(41.8,10.8)]),
 (p.F_Cu,[(41.8,45.2),(48,45.2),(48,49),(58,49),(58,53.5),(41.8,53.5)]),
 (p.B_Cu,[(17.2,7),(79.5,7),(79.5,53.5),(38,53.5),(38,15),(17.2,15)])]:
    z=p.ZONE(b);z.SetLayer(layer);z.SetNet(nets['FPGA_VIN']);z.SetLocalClearance(p.FromMM(.2));z.SetMinThickness(p.FromMM(.2));z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS);z.Outline().NewOutline()
    for x,y in points:z.Outline().Append(v(x,y))
    b.Add(z)
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());save_board(str(PATH),b)
accepted=[]
for x,y in [(19.6,7.5),(20.6,7.5),(21.6,7.5),(22.6,7.5),(43,9),(44,9),(45,9),(43,48),(44,48),(45,48)]:
    if any(isinstance(t,p.PCB_VIA) and t.GetNetname()=='FPGA_VIN' and t.GetPosition()==v(x,y) for t in b.GetTracks()):
        accepted.append([x,y]);continue
    t=p.PCB_VIA(b);t.SetPosition(v(x,y));t.SetWidth(p.FromMM(.6));t.SetDrill(p.FromMM(.3));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(nets['FPGA_VIN']);b.Add(t)
    p.ZONE_FILLER(b).Fill(b.Zones());save_board(str(PATH),b)
    out=F/'power-via-trial.json';subprocess.run(['kicad-cli','pcb','drc','--format','json','-o',str(out),str(PATH)],check=True,stdout=subprocess.DEVNULL)
    j=json.loads(out.read_text())
    if j['violations'] or j['unconnected_items']:b.Delete(t)
    else:accepted.append([x,y]);t.SetLocked(True)
p.ZONE_FILLER(b).Fill(b.Zones());save_board(str(PATH),b)
(F/'power-distribution.json').write_text(json.dumps({'additional_parallel_vias_mm':accepted,'note':'Parallel copper improves supply routing; thermal and extracted resistance signoff pending'},indent=2))
print('Added module supply planes; accepted parallel vias:',accepted)
