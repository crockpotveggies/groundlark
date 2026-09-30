"""Burrowlark population boundary, independent of placement/BOM generation."""


def population(references):
    references = set(references)
    removed = references & {'U3', 'C5'}
    if removed:
        raise ValueError(f'Burrowlark retains removed infrasound parts: {sorted(removed)}')
    if not {'U6', 'C10'} <= references:
        raise ValueError('Burrowlark requires SHT45 U6 and bypass C10')
    if 'U2' not in references or 'C4' not in references:
        raise ValueError('Burrowlark requires the RM3100 module and its bypass capacitor')


def climate_pins(pins):
    expected = {('U6', '1'): 'SDA', ('U6', '2'): 'SCL',
                ('U6', '3'): 'V3_SENSOR', ('U6', '4'): 'GND',
                ('C10', '1'): 'V3_SENSOR', ('C10', '2'): 'GND'}
    for pin, net in expected.items():
        if pins.get(pin) != net:
            raise ValueError(f'SHT45 pin {pin} must connect to {net}')
