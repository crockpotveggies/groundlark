"""Burrowlark population boundary, independent of placement/BOM generation."""


def magnetometer_only(references):
    references = set(references)
    removed = references & {'U3', 'C5'}
    if removed:
        raise ValueError(f'Burrowlark retains removed infrasound parts: {sorted(removed)}')
    if 'U2' not in references or 'C4' not in references:
        raise ValueError('Burrowlark requires the RM3100 module and its bypass capacitor')
