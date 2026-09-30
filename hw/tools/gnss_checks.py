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
    ('U140','1'):'PI_5V',('U140','2'):'GND',('U140','5'):'GNSS_BIAS'})
NC=[('U21',str(n)) for n in (2,3,6,9,13,14,15,18)]+[('U140','3'),('U140','4')]
for ref,net in [('C146','PI_3V3'),('C147','PI_3V3'),('C149','PI_5V'),('C150','GNSS_BIAS')]:
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
    return dict(pin_checks=checks,deliberate_no_connects=len(NC),pps_bcm=24,
        antenna='3.3 V active SMA, <=20 mA; 50 ohm connector',sample_timing_qualified=False,
        rf_qualified=False,receiver_peak_allocation_mA=100,antenna_allocation_mA=20)
