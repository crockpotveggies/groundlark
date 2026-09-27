"""Read-only stock construction checks, independent of placement metadata."""
import math
import sexpdata as sx

def stackup(text):
    def children(node,key):return [x for x in node if isinstance(x,list) and x and str(x[0])==key]
    tree=sx.loads(text);setup=children(tree,'setup')[0];stack=children(setup,'stackup')[0]
    layers=children(stack,'layer')
    actual={str(x[1]):float(children(x,'thickness')[0][1]) for x in layers if children(x,'thickness')}
    expected={'F.Cu':.035,'In1.Cu':.0152,'In2.Cu':.0152,'B.Cu':.035,'dielectric 1':.2104,'dielectric 2':1.065,'dielectric 3':.2104}
    assert {n for n in actual if n.endswith('.Cu')}=={'F.Cu','In1.Cu','In2.Cu','B.Cu'},'Four-layer physical stackup'
    for name,value in expected.items():assert name in actual and math.isclose(actual[name],value,abs_tol=1e-7),('JLC04161H-7628 stock stack',name)
    assert str(children(stack,'dielectric_constraints')[0][1])=='no','No custom lamination'
    return {'stock_id':'JLC04161H-7628','nominal_order_thickness_mm':1.6,'copper_dielectric_total_mm':sum(expected.values()),'copper_mm':[.035,.0152,.0152,.035],'dielectric_mm':[.2104,1.065,.2104]}

def review(board):
    import pcbnew as p
    assert board.GetCopperLayerCount()==4,'Four copper layers'
    assert math.isclose(p.ToMM(board.GetDesignSettings().GetBoardThickness()),1.6,abs_tol=.0001),'Nominal board thickness'
    vias=[t for t in board.GetTracks() if isinstance(t,p.PCB_VIA)]
    smd=[(f,q) for f in board.GetFootprints() for q in f.Pads() if q.GetAttribute()==p.PAD_ATTRIB_SMD]
    for via in vias:
        assert via.GetViaType()==p.VIATYPE_THROUGH and via.TopLayer()==p.F_Cu and via.BottomLayer()==p.B_Cu,'Through-vias only'
        assert via.GetDrillValue()>=p.FromMM(.3) and via.GetWidth(p.F_Cu)>=p.FromMM(.6),'Standard via drill/annulus'
        hole=p.SHAPE_CIRCLE(via.GetPosition(),via.GetDrillValue()//2)
        for fp,pad in smd:
            assert not p.SHAPE.Collide(hole,pad.GetEffectiveShape(fp.GetLayer()),p.FromMM(.05)),('No via-in-SMT-pad',fp.GetReference(),pad.GetNumber())
    return {'through_vias':len(vias),'minimum_via_diameter_mm':.6,'minimum_via_drill_mm':.3,'via_in_smt_pad':0,'filled_capped_vias_required':False}
