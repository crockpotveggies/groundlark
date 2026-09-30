"""Independent MAX-M10S pin and SMA drawing fixtures; no RF qualification."""
from collections import Counter
import math

PINS={('U21',str(n)):net for n,net in {
    1:'GND',4:'GNSS_PPS',5:'GND',7:'PI_3V3',8:'PI_3V3',10:'GND',
    11:'GNSS_RF',12:'GND',16:'PI_I2C_SDA',17:'PI_I2C_SCL'}.items()}
PINS.update({('J1','18'):'GNSS_PPS',('J140','1'):'GNSS_ANT',('J140','2'):'GND',
    ('C148','1'):'GNSS_ANT',('C148','2'):'GNSS_RF',
    ('L140','1'):'GNSS_BIAS',('L140','2'):'GNSS_ANT',
    ('D140','1'):'GNSS_ANT',('D140','2'):'GND',
    ('U140','1'):'PI_5V',('U140','2'):'GND',('U140','5'):'GNSS_LDO',
    ('U141','1'):'GNSS_LDO',('U141','2'):'GND',('U141','3'):'GNSS_LDO',
    ('U141','5'):'GNSS_LDO',('U141','6'):'GNSS_BIAS',
    ('U43','1'):'SENS_3V3',('U43','2'):'I2C_SDA',('U43','3'):'I2C_SCL',
    ('U43','6'):'PI_I2C_SCL',('U43','7'):'PI_I2C_SDA',('U43','8'):'PI_3V3',
    ('C48','1'):'SENS_3V3',('C49','1'):'PI_3V3'})
NC=[('U21',str(n)) for n in (2,3,6,9,13,14,15,18)]+[('U140','3'),('U140','4'),('U141','4')]
for ref,net in [('C146','PI_3V3'),('C147','PI_3V3'),('C149','PI_5V'),('C150','GNSS_LDO'),('C151','GNSS_BIAS'),('C152','GNSS_LDO')]:
    PINS[ref,'1']=net;PINS[ref,'2']='GND'


def verify(pins):
    for key,net in PINS.items():
        if pins.get(key)!=net:raise ValueError(f'GNSS pin mismatch: {key}')
    degree=Counter(pins.values())
    for key in NC:
        if not pins.get(key) or degree[pins[key]]!=1:raise ValueError(f'GNSS no-connect: {key}')
    if degree['GNSS_PPS']!=2:raise ValueError('PPS must connect only U21 and BCM24')
    return len(PINS)


def verify_board(board):
    import pcbnew as p
    fps={f.GetReference():f for f in board.GetFootprints()}
    pins={(f.GetReference(),q.GetNumber()):q.GetNetname() for f in fps.values() for q in f.Pads() if q.GetNumber()}
    checks=verify(pins)
    sma=fps['J140'];xy=lambda q:(p.ToMM(q.x),p.ToMM(q.y))
    assert not sma.IsFlipped() and sma.GetOrientationDegrees()%360==0,'SMA must face native -X wall'
    assert math.dist(xy(sma.GetPosition()),(54,65.8))<.001,'SMA enclosure position'
    grounds=[]
    for pad in sma.Pads():
        local=(p.ToMM(pad.GetPosition().x)-54,p.ToMM(pad.GetPosition().y)-65.8)
        if pad.GetNumber()=='1':
            assert math.hypot(*local)<.001 and abs(p.ToMM(pad.GetDrillSize().x)-1.2)<.001
        else:
            grounds.append(tuple(round(x,2) for x in local))
            assert abs(p.ToMM(pad.GetDrillSize().x)-1.5)<.001
    assert set(grounds)=={(-2.55,-2.55),(-2.55,2.55),(2.55,-2.55),(2.55,2.55)},'SMA drawing pad pitch'
    assert fps['U21'].IsFlipped(),'GNSS underside clearance'
    assert fps['U21'].GetValue()=='MAX-M10S-00B'
    assert fps['D140'].GetValue()=='PESD5V0F1BL'
    rf=[t for t in board.GetTracks() if t.GetNetname()=='GNSS_RF']
    assert rf and all(not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.B_Cu for t in rf),'RF path must stay on B.Cu'
    assert sum(p.ToMM(t.GetLength()) for t in rf)<3,'RF input stub too long'
    # TI TPS2553 DBV top-view terminal drawing: FAULT=4, ILIM=5.
    limiter=fps['U141'];assert not limiter.IsFlipped() and limiter.GetOrientationDegrees()%360==0
    assert limiter.GetValue()=='TPS2553'
    for number,(x,y) in {'1':(-1.1375,-.95),'2':(-1.1375,0),'3':(-1.1375,.95),
                         '4':(1.1375,.95),'5':(1.1375,0),'6':(1.1375,-.95)}.items():
        q=next(q for q in limiter.Pads() if q.GetNumber()==number)
        pos=q.GetPosition()-limiter.GetPosition()
        assert math.dist(xy(pos),(x,y))<.001,'TPS2553 DBV numbered pads'
    from imu_layout import Copper
    def pad(ref,num):return next(q for q in fps[ref].Pads() if q.GetNumber()==str(num))
    assert fps['C151'].GetValue()=='10n' and not fps['C151'].IsDNP()
    assert fps['C152'].GetValue()=='100n' and not fps['C152'].IsDNP()
    bypass=Copper(board,'GNSS_BIAS').between(pad('L140',1),pad('C151',1))
    assert bypass<=2,'L140 RF bypass must be local'
    input_bypass=Copper(board,'GNSS_LDO').between(pad('U141',1),pad('C152',1))
    assert input_bypass<=6,'TPS2553 input bypass path too long'
    layer=board.GetLayerID('In1.Cu')
    planes=[z.GetFilledPolysList(layer) for z in board.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(layer)]
    stitches=[t.GetPosition() for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND'
              and t.IsOnLayer(layer) and any(poly.Contains(t.GetPosition()) for poly in planes)]
    ground_path=Copper(board,'GND').to_stitch(pad('C151',2),stitches)
    assert ground_path<=2,'C151 ground return must reach a local connected plane stitch'
    return dict(pin_checks=checks,deliberate_no_connects=len(NC),pps_bcm=24,
        antenna='3.3 V active SMA, <=20 mA; 50 ohm connector',sample_timing_qualified=False,
        sustained_short_limit_mA=[50,100],choke_rated_mA=280,
        rf_bypass_path_mm=bypass,rf_bypass_ground_path_mm=ground_path,input_bypass_path_mm=input_bypass,
        host_bus_low_margin_V=.63-.4,
        rf_qualified=False,receiver_peak_allocation_mA=100,antenna_allocation_mA=20)
