"""Explicitly author local analog/bypass routes before the general router.

This is an authoring command, never a read-only check. All vias are ordinary
0.3 mm drilled through-vias outside SMT pads; the two inner layers are ground.
"""
import math
import pcbnew as p
from project_paths import board_dir
from kicad_support import v, save_board
from assemble_pcb import export_dsn

def main():
    folder=board_dir('skylark-usb');path=folder/'skylark-usb.kicad_pcb'
    b=p.LoadBoard(str(path));fps={f.GetReference():f for f in b.GetFootprints()};nets=b.GetNetsByName()
    def route(net,pts,layer=p.B_Cu,width=.15):
        for a,z in zip(pts,pts[1:]):
            t=p.PCB_TRACK(b);t.SetStart(v(a[0]+50,a[1]+50));t.SetEnd(v(z[0]+50,z[1]+50));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(nets[net]);t.SetLocked(True);b.Add(t)
    # SO2 local feedback with 1206 C0G capacitors.
    route('SO2_WE_SUM',[(21.775,25.5),(22.5,25.5),(22.5,26.5),(20.5,26.5),(20.5,30.525),(17,30.525)])
    route('SO2_WE_SUM',[(21.8,29.325),(20.5,29.325)])
    route('SO2_WE_SUM',[(19,31.225),(19,30.525)])
    route('SO2_WE_OUT',[(21.8,29.975),(21,29.975),(21,32),(19.525,33.475),(17,33.475)])
    route('SO2_WE_OUT',[(19,32.775),(19,33.475)])
    route('SO2_AE_SUM',[(26.2,28.675),(27.4,28.675),(27.55,28.525),(31,28.525)])
    route('SO2_AE_SUM',[(29,29.225),(29,28.525)])
    route('SO2_AE_SUM',[(30.775,26),(32.2,26),(32.2,28.525),(31,28.525)])
    route('SO2_AE_OUT',[(26.2,29.325),(27.6,29.325),(28,29.725),(28,31.475),(31,31.475)])
    route('SO2_AE_OUT',[(29,30.775),(29,31.475)])
    # Five 100 nF C0G capacitors in parallel per H2S channel. Keep the first
    # capacitor close to the amplifier; paired short buses feed the others.
    route('H2S_WE_SUM',[(63.775,25.5),(64.5,25.5),(64.5,26.5),(62.5,26.5),(62.5,29.325),(63.8,29.325)])
    route('H2S_WE_SUM',[(62.5,29.325),(62.5,32),(61.475,33),(61.475,43)])
    route('H2S_WE_SUM',[(61,29.225),(62.5,29.225)])
    route('H2S_WE_OUT',[(63.8,29.975),(63.3,29.975),(63.3,32.4),(62.8,32.9),(62.8,44.5),(58.525,44.5),(58.525,33)])
    route('H2S_WE_OUT',[(61,30.775),(60.2,30.775),(58.525,32.45),(58.525,33)])
    route('H2S_AE_SUM',[(68.2,28.675),(70,28.675),(70.45,28.225),(71,28.225),(71.75,28.225),(73.025,29),(73.025,39)])
    route('H2S_AE_SUM',[(72.775,26),(73.3,26),(73.3,27.5),(73.025,28.275),(73.025,29)])
    route('H2S_AE_OUT',[(68.2,29.325),(69.5,29.325),(70,29.825),(71,29.825),(71,40.5),(75.975,40.5),(75.975,29)])
    route('H2S_AE_OUT',[(71,29.775),(71,29.825)])
    # Supply bypasses are authored first so other nets cannot force detours.
    for shift in [0,42]:
        route('VA',[(24.725,32),(24.725,31.45),(26.2,29.975)] if shift==0 else [(26.725+shift,32),(26.725+shift,30.5),(26.2+shift,29.975)])
        route('VA',[(18.5+shift,27.775),(17+shift,27.775),(16.1375+shift,27.95)])
    for net,pts in [('VA',[(57,54.775),(56.1,54.775),(56.1,54.325),(54.8625,54.325)]),('V3',[(57,51.775),(56.1,51.775),(56.1,53.675),(54.8625,53.675)]),('REF_2V5',[(56.525,57.5),(55.8,57.5),(55.8,56.275),(54.8625,56.275)]),('VA',[(41.925,52),(40.1375,52.05)])]:route(net,pts,p.F_Cu)
    def pad(ref,pin):return next(q for q in fps[ref].Pads() if q.GetNumber()==str(pin))
    def point(q):return (p.ToMM(q.GetPosition().x)-50,p.ToMM(q.GetPosition().y)-50)
    for ref,pin,cap in [('U1',9,'C6'),('U1',24,'C7'),('U1',48,'C8'),('U1',36,'C9'),('U2',1,'C1'),('U2',5,'C2'),('U3',1,'C3'),('U3',6,'C4')]:
        a=pad(ref,pin);c=pad(cap,1);route(a.GetNetname(),[point(a),point(c)],p.F_Cu)
    # Make a short ground return beside every SMD ground pad when possible.
    # Collision checks include the other face and prohibit via-in-pad.
    def free(shape,layer,net,via=False):
        for f in b.GetFootprints():
            for q in f.Pads():
                if q.GetNetname()==net and not via:continue
                if layer is None or q.IsOnLayer(layer):
                    if p.SHAPE.Collide(shape,q.GetEffectiveShape(q.GetLayer()),p.FromMM(.155)):return False
        for t in b.GetTracks():
            if t.GetNetname()==net:continue
            if layer is None or t.IsOnLayer(layer):
                if p.SHAPE.Collide(shape,t.GetEffectiveShape(),p.FromMM(.155)):return False
        return True
    missing=[]
    for f in b.GetFootprints():
        if f.GetReference() in ('U11','C70'):continue
        for q in f.Pads():
            if q.GetNetname()!='GND' or q.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
            pos=q.GetPosition();layer=f.GetLayer();found=False
            for radius in [.65,.8,1,1.2,1.4,1.6,1.8,2]:
                for deg in range(0,360,15):
                    xy=v(p.ToMM(pos.x)+radius*math.cos(math.radians(deg)),p.ToMM(pos.y)+radius*math.sin(math.radians(deg)))
                    if not free(p.SHAPE_CIRCLE(xy,p.FromMM(.3)),None,'GND',True) or not free(p.SHAPE_SEGMENT(pos,xy,p.FromMM(.15)),layer,'GND'):continue
                    if any(isinstance(t,p.PCB_VIA) and (xy-t.GetPosition()).EuclideanNorm()<p.FromMM(.65) for t in b.GetTracks()):continue
                    t=p.PCB_TRACK(b);t.SetStart(pos);t.SetEnd(xy);t.SetWidth(p.FromMM(.15));t.SetLayer(layer);t.SetNet(nets['GND']);t.SetLocked(True);b.Add(t)
                    t=p.PCB_VIA(b);t.SetPosition(xy);t.SetWidth(p.FromMM(.6));t.SetDrill(p.FromMM(.3));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(nets['GND']);t.SetLocked(True);b.Add(t)
                    found=True;break
                if found:break
            if not found:missing.append((f.GetReference(),q.GetNumber()))
    save_board(str(path),b);export_dsn(b,folder/'skylark-usb.dsn',(.6,.3),['In1.Cu','In2.Cu'])
    print('Local routes authored; ground pads without a direct stitch:',missing)

if __name__=='__main__':main()
