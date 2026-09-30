"""Independent supply/control pin fixture from TI MSPM0L110x, TPS709,
TPSM53603 and TPS22953 data sheets; Nexperia 2N7002 SOT23 pin table.

These checks do not qualify battery thresholds, startup, thermals or noise.
"""
from collections import Counter

PINS = {
 ('U130','3'):'SUP_NRST', ('U130','4'):'SUP_3V3', ('U130','5'):'GND',
 ('U130','7'):'SUP_RUN_DRIVE', ('U130','8'):'SUP_REQUEST', ('U130','9'):'SUP_ACK_N',
 ('U130','23'):'SUP_SWDIO', ('U130','24'):'SUP_SWCLK', ('U130','31'):'SUP_BAT_ADC',
 ('U130','32'):'SUP_CORE', ('U130','33'):'GND',
 ('U131','1'):'BAT_PROTECTED', ('U131','2'):'GND', ('U131','5'):'SUP_3V3',
 ('U132','1'):'BAT_PROTECTED', ('U132','14'):'BAT_PROTECTED', ('U132','2'):'SUP_RUN',
 ('U132','7'):'PI_RAW_5V', ('U132','8'):'PI_RAW_5V', ('U132','9'):'PI_BUCK_FB',
 ('U133','1'):'PI_RAW_5V', ('U133','2'):'PI_RAW_5V', ('U133','3'):'PI_RAW_5V',
 ('U133','4'):'SUP_RUN', ('U133','5'):'GND', ('U133','6'):'PI_SWITCH_CT',
 ('U133','8'):'PI_RAW_5V', ('U133','9'):'PI_5V', ('U133','10'):'PI_5V', ('U133','11'):'GND',
 ('J130','1'):'BAT_INPUT', ('J130','2'):'GND',
 ('F130','1'):'BAT_INPUT', ('F130','2'):'BAT_FUSED',
 ('D130','1'):'BAT_PROTECTED', ('D130','2'):'BAT_FUSED',
 ('D131','1'):'BAT_PROTECTED', ('D131','2'):'GND',
 ('Q130','1'):'SUP_REQUEST', ('Q130','2'):'GND', ('Q130','3'):'PI_SHUTDOWN_N',
 ('Q131','1'):'PI_HALTED', ('Q131','2'):'GND', ('Q131','3'):'SUP_ACK_N',
 ('J1','31'):'PI_SHUTDOWN_N', ('J1','33'):'PI_HALTED', ('J1','2'):'PI_5V', ('J1','4'):'PI_5V',
 ('R138','1'):'PI_3V3', ('R138','2'):'PI_SHUTDOWN_N',
 ('R140','1'):'SUP_3V3', ('R140','2'):'SUP_ACK_N',
 ('R132','1'):'SUP_RUN', ('R132','2'):'GND',
 ('R141','1'):'SUP_RUN_DRIVE', ('R141','2'):'SUP_RUN',
 ('R130','1'):'PI_RAW_5V', ('R130','2'):'PI_BUCK_FB',
 ('R131','1'):'PI_BUCK_FB', ('R131','2'):'GND',
 ('R135','1'):'BAT_FUSED', ('R135','2'):'SUP_BAT_ADC',
 ('R136','1'):'SUP_BAT_ADC', ('R136','2'):'GND',
 ('C143','1'):'SUP_CORE', ('C143','2'):'GND',
 ('J131','1'):'SUP_3V3', ('J131','2'):'GND', ('J131','3'):'SUP_SWCLK',
 ('J131','4'):'SUP_SWDIO', ('J131','5'):'SUP_NRST',
}
for pin in ('3','10','11','12','15'):PINS['U132',pin]='GND'
NC = [('U131','3'),('U131','4'),('U132','4'),('U132','5'),('U132','6'),('U132','13'),('U133','7')]
NC += [('U130',str(n)) for n in range(1,34) if ('U130',str(n)) not in PINS]


def verify(pins):
    for key, net in PINS.items():
        if pins.get(key) != net:raise ValueError(f'Pi power/control pin mismatch: {key}')
    degree = Counter(pins.values())
    for key in NC:
        if not pins.get(key) or degree[pins[key]] != 1:
            raise ValueError(f'Required no-connect changed: {key}')
    if degree['SUP_CORE'] != 2:raise ValueError('VCORE must drive only its tank capacitor')
    return len(PINS)


def budget(current_a=3, switch_ohm=.025, copper_ohm=.05):
    if not 0 <= current_a <= 3:raise ValueError('Pi and HAT combined allocation is 3 A')
    # TPSM53603 full-temperature reference +/-1.5%; 0.1% resistors, 50 nA FB bias.
    low=.985*(1+10000*.999/(2410*1.001))-50e-9*10000*1.001
    high=1.015*(1+10000*1.001/(2410*.999))+50e-9*10000*1.001
    return dict(nominal_V=1+10000/2410, minimum_V=low-current_a*(switch_ohm+copper_ohm),
                maximum_V=high, total_A=current_a, input_range_V=[8,18],
                input_scenario_A=(1+10000/2410)*current_a/(7.5*.85),
                adc_at_18V=18*150000*1.001/(1000000*.999+150000*1.001),
                copper_budget_ohm=copper_ohm, switch_budget_ohm=switch_ohm,
                measured=False)


def verify_board(board, spec):
    import pcbnew as p
    pins={(f.GetReference(),q.GetNumber()):q.GetNetname() for f in board.GetFootprints() for q in f.Pads() if q.GetNumber()}
    checks=verify(pins); fps={f.GetReference():f for f in board.GetFootprints()};meta={x['ref']:x for x in spec['parts']}
    for ref,mpn in {'U130':'MSPM0L1105TRHBR','U131':'TPS70933DBVR','U132':'TPSM53603RDAR','U133':'TPS22953DQCR','J130':'1803277','F130':'0467004.NR'}.items():
        assert meta[ref]['mpn']==mpn and not fps[ref].IsDNP(),ref
    for ref,value in {'C143':'470n','R130':'10k','R131':'2.41k','R135':'1M','R136':'150k'}.items():assert fps[ref].GetValue()==value,ref
    assert fps['J130'].GetOrientationDegrees()%360==180 and not fps['J130'].IsFlipped()
    pads={q.GetNumber():q for q in fps['U133'].Pads() if q.GetNumber()}
    assert abs(p.ToMM(pads['11'].GetSize().x)-.84)<.001 and abs(p.ToMM(pads['11'].GetSize().y)-2.4)<.001
    b=budget();assert b['minimum_V']>4.75 and b['maximum_V']<5.25 and b['adc_at_18V']<2.5,b
    return dict(pin_checks=checks,deliberate_no_connects=len(NC),spare_bcm=[],budget=b,firmware='configuration placeholder; MCU implementation pending',physical_qualification=False)
