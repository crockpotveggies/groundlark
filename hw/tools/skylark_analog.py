"""Read-only analog design and local copper checks; not sensor qualification.

Limits are project engineering targets. The sensor's impedance, leakage and
environmental noise must be measured; a nominal RC calculation is not a noise
floor or a potentiostat stability result.
"""
import math
from imu_layout import Copper, shortest


def number(value):
    for suffix, scale in [('uF', 1e-6), ('nF', 1e-9), ('R', 1)]:
        if value.endswith(suffix):
            return float(value[:-len(suffix)]) * scale
    raise ValueError(value)


def review(board):
    import pcbnew as p
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    def value(ref):
        return number(fps[ref].GetValue())
    def pad(ref, pin):
        return next(q for q in fps[ref].Pads() if q.GetNumber() == str(pin))
    for ref in ('U5', 'U8', 'U10'):
        assert fps[ref].GetValue() == 'OPA387DBVR', 'Analog amplifier selection'
    for ref in ('U7', 'U9'):
        assert fps[ref].GetValue() == 'OPA2387DGKR', 'Analog amplifier selection'
        assert 'VSSOP-8_3x3mm_P0.65mm' in str(fps[ref].GetFPID().GetLibItemName()), 'Amplifier package'
    rows = []
    for gas, base, amp, sensitivity, maximum, span in [
        ('SO2', 30, 'U7', .4e-6, .5e-6, 20),
        ('H2S', 50, 'U9', 1.7e-6, 2.1e-6, 25),
    ]:
        poles = []
        for offset, el, pin in [(0, 'WE', 2), (3, 'AE', 6)]:
            caps=[f'C{base+offset}']
            if gas=='H2S':caps += [f'C{x}' for x in range(80 if el=='WE' else 84,84 if el=='WE' else 88)]
            rf, cf = value(f'R{base+offset+1}'), sum(value(c) for c in caps)
            ro, co = value(f'R{base+offset+2}'), value(f'C{base+offset+1}')
            feedback_hz = 1/(2*math.pi*rf*cf)
            output_hz = 1/(2*math.pi*ro*co)
            assert 12 <= feedback_hz <= 20, 'Gas feedback bandwidth'
            assert ro <= 10000, 'ADC source resistance / bias-current error'
            assert 1.2 <= output_hz <= 2, 'Gas ADC filter bandwidth'
            poles.append((feedback_hz, output_hz))
            net = gas+'_'+el+'_SUM'
            items = [t for t in board.GetTracks() if t.GetNetname() == net]
            assert items and all(isinstance(t,p.PCB_TRACK) and t.GetLayer()==p.B_Cu for t in items), 'TIA summing route layer/via'
            length = sum(p.ToMM(t.GetLength()) for t in items)
            # Parallel C0G bank adds a 10 mm bus. Keep the amplifier-to-first
            # feedback path local and bound the total capacitive pickup area.
            assert length <= (26 if gas=='H2S' else 16), 'TIA summing copper length'
            # Reject disconnected local feedback even if another copper layer
            # could provide a roundabout route after an edit.
            copper = Copper(board, net)
            assert copper.between(pad(amp,pin),pad(f'C{base+offset}',1)) <= 7, 'TIA local feedback path'
            for cap in caps:
                assert math.isclose(value(cap),100e-9,rel_tol=1e-9), 'C0G feedback capacitance'
                assert '1206' in str(fps[cap].GetFPID().GetLibItemName()), 'C0G feedback package'
            adc_net = gas+'_'+el+'_ADC'
            adc_copper = [t for t in board.GetTracks() if t.GetNetname()==adc_net]
            assert sum(p.ToMM(t.GetLength()) for t in adc_copper if isinstance(t,p.PCB_TRACK)) <= 16, 'ADC filtered trace length'
            attenuation = -10*math.log10((1+(50/feedback_hz)**2)*(1+(50/output_hz)**2))
            rows.append(dict(channel=gas+' '+el, feedback_pole_hz=feedback_hz,
                             adc_pole_hz=output_hz, nominal_50Hz_signal_attenuation_dB=attenuation,
                             summing_copper_mm=length, sensitivity_V_per_ppm=sensitivity*rf))
        assert poles[0] == poles[1], 'Working/auxiliary filter mismatch'
        # 0.1% feedback tolerance; reserve 100 mV for offset/over-range margin.
        excursion = maximum*span*value(f'R{base+1}')*1.001
        assert 1.25+excursion+.1 < 2.5*.998, 'Gas ADC positive headroom'
        assert 1.25-excursion > .15, 'Gas negative headroom'

    # Conservative 8 mA analog rail envelope includes seven op amps at 700 uA
    # each, ADC/reference, divider and electrode/output currents.
    minimum_va = 3.234 - .008*(value('R19')*1.01+.1)
    assert minimum_va >= 3.05, 'Analog supply drop'
    # 0.5 V diode drop is a conservative design allowance, to qualify over
    # temperature. J270 cutoff maximum is 2 V at its specified test conditions.
    gate_overdrive = (4.35-.5-1.2525)*value('R71')*.999/(value('R70')*1.001+value('R71')*.999)
    gate_min=1.2525+gate_overdrive
    assert gate_overdrive >= 2+.3, 'Electrode clamp turn-off margin'

    # Supply paths must be short and stay on the device side. A ground stitch
    # must actually land in filled In1.Cu, not merely exist nearby.
    inner=p.In1_Cu
    planes=[z.GetFilledPolysList(inner) for z in board.Zones() if z.GetNetname()=='GND' and not z.GetIsRuleArea() and z.IsOnLayer(inner)]
    stitches=[t for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and any(z.Contains(t.GetPosition()) for z in planes)]
    ground=Copper(board,'GND');bypass=[]
    for ref,pin,cap,limit in [('U5',5,'C16',3),('U6',12,'C17',3.5),('U6',13,'C18',4.5),('U6',9,'C19',4),('U7',8,'C37',3),('U8',5,'C38',3),('U9',8,'C57',3),('U10',5,'C58',3),('U1',9,'C6',3),('U1',24,'C7',3),('U1',36,'C9',3),('U1',48,'C8',3),('U2',1,'C1',3),('U2',5,'C2',3),('U3',1,'C3',3),('U3',6,'C4',3)]:
        a,c,g=pad(ref,pin),pad(cap,1),pad(cap,2)
        layer=fps[ref].GetLayer()
        assert layer==fps[cap].GetLayer(), 'Analog bypass layer'
        supply=Copper(board,a.GetNetname())
        same={key:[(dest,length) for dest,length in edges if dest[2]==layer] for key,edges in supply.graph.items() if key[2]==layer}
        length=shortest(same,supply.at_pad(a),set(supply.at_pad(c)))
        assert length <= limit, 'Analog bypass supply path'
        goals={(t.GetPosition().x,t.GetPosition().y,layer) for t in stitches}
        distance=shortest(ground.graph,ground.at_pad(g),goals)
        assert distance <= 2, 'Analog bypass ground return'
        bypass.append(dict(device=ref,capacitor=cap,supply_mm=length,ground_to_plane_mm=distance))
    mcu_ground={}
    for pin in (8,23,35,47):
        distance=shortest(ground.graph,ground.at_pad(pad('U1',pin)),{(t.GetPosition().x,t.GetPosition().y,p.F_Cu) for t in stitches})
        assert distance<=2,'MCU local ground return'
        mcu_ground[str(pin)]=distance
    guard={}
    for layer in (p.F_Cu,p.B_Cu):
        polygons=[z.GetFilledPolysList(layer) for z in board.Zones() if z.GetNetname()=='GUARD' and not z.GetIsRuleArea() and z.IsOnLayer(layer)]
        assert polygons and any(poly.OutlineCount() for poly in polygons),'Driven guard copper on both faces'
        if layer!=p.F_Cu:continue
        for cell in ('GS1','GS2'):
            for el in ('WE','RE','AE'):
                center=pad(cell,el).GetPosition();covered=0
                for i in range(48):
                    angle=2*math.pi*(i+.5)/48
                    q=p.VECTOR2I(center.x+round(p.FromMM(2.6)*math.cos(angle)),center.y+round(p.FromMM(2.6)*math.sin(angle)))
                    covered+=any(poly.Contains(q) for poly in polygons)
                assert covered>=36,'Socket guard coverage'
                guard[cell+'.'+el]=covered/48
    return dict(channels=rows,bypass=bypass,analog_supply_min_V=minimum_va,
                analog_current_budget_mA=8,clamp_gate_min_V=gate_min,mcu_ground_to_plane_mm=mcu_ground,socket_guard_fraction=guard,
                scope='Calculated signal filtering and CAD geometry only; no qualified detection limit or cell stability model')
