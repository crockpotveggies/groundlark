"""Independent DLVR fixture: All Sensors DS-0300 Rev J, pages 3, 13 and 14.

The four-pin E1BS drawing is a front pin view, with 2.54 mm lead pitch.
The conservative package envelope includes both pressure barbs. It is not a
supplier solid or a qualification of tubing, temperature drift or vibration.
"""
from collections import Counter

PINS = {('U23','1'):'GND', ('U23','2'):'SENS_3V3',
        ('U23','3'):'I2C_SDA', ('U23','4'):'I2C_SCL',
        ('C24','1'):'SENS_3V3', ('C24','2'):'GND'}
MPN = 'DLVR-F50D-E1BS-I-NI3F'


def verify(pins, pads, pose, mpn, dnp):
    for key, net in PINS.items():
        if pins.get(key) != net:
            raise ValueError(f'DLVR physical pin / supply mismatch: {key}')
    if mpn != MPN or dnp:
        raise ValueError('DLVR must be the fitted 3.3 V I2C fast E1BS variant')
    if pose != (270, False):
        raise ValueError('DLVR pin view / port orientation changed')
    expected = {'1':(1.5,26), '2':(1.5,28.54), '3':(1.5,31.08), '4':(1.5,33.62)}
    if set(pads) != set(expected) or any(len(pads[k]) != 2 or any(abs(a-b)>1e-5 for a,b in zip(pads[k],v)) for k,v in expected.items()):
        raise ValueError('DLVR numbered lead geometry changed')
    for pin,net in {'18':'GNSS_PPS','31':'PI_SHUTDOWN_N','33':'PI_HALTED'}.items():
        if pins.get(('J1',pin)) != net:
            raise ValueError('Reserved GNSS/power-management GPIO changed')
    return dict(physical_pin_checks=len(PINS), i2c_address='0x28',
                existing_bus_addresses=['0x20','0x40','0x42'], additional_pi_pins=0,
                reserved_bcm=[6,13,24], maximum_fast_current_mA=4.3,
                # Rotated conservative 12.70 + 2.11 by 9.15 mm package.
                body_and_barbs_xy_mm=[1.5,23.27,10.65,38.08],
                minimum_module_xy_clearance_mm=19.35,
                physical_qualification=False)
