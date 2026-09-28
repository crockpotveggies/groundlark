"""Read-only sensor-to-recording response budget for the two active boards.

Analog transfer functions use routed PCB values. ADC magnitudes are approximate
readings of TI SBAS751B figures 45/50, not invented FIR coefficients. Unknown
phase, cell impedance and enclosure dynamics remain unknown in the report.
Run in the portable lab; no CAD is modified and no physical pass is asserted.
"""
import argparse
import ast
import cmath
import hashlib
import itertools
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TI = 'https://www.ti.com/lit/ds/symlink/ads122c04.pdf'
ST = 'https://www.st.com/resource/en/application_note/DM00517282-.pdf'
SGX = 'https://sgxsensortech.com/uploads/f_note/'
# Rounded plot readings; below plot resolution use 0 dB, NOT a flatness claim.
# No interpolation across filter notches. Only these checkpoints are supported.
ADC_PLOTS = {
    330: {1: 0, 4.5: 0, 10: 0, 27: 0, 50: -.3, 100: -1.3,
          150.1: -3., 164.313: -3.7, 200: -5.7, 300: -18.7,
          318.626: -26.2, 400: -15.1, 500: -11.3},
    20: {.01: 0, .1: 0, 1: 0, 2.0833333: 0, 4.1666667: 0, 10: -1.7,
         13.1: -2.9, 20: -7., 25: -11.3, 40: -36.},
}


def db(h):
    return 20 * math.log10(abs(h)) if abs(h) else None


def phase(h):
    return math.degrees(cmath.phase(h))


def lowpass(f, tau):
    return 1 / (1 + 2j * math.pi * f * tau)


def folded(f, rate):
    if f < 0 or rate <= 0:
        raise ValueError('positive sample rate and nonnegative frequency required')
    return abs((f + rate / 2) % rate - rate / 2)


def geophone(f, rseries, bias, capacitance, coil=395, f0=4.5, damping=.7):
    s = 2j * math.pi * f
    wn = 2 * math.pi * f0
    mechanical = s*s / (s*s + 2*damping*wn*s + wn*wn)
    load = bias / (bias + coil + rseries)
    electrical = load * lowpass(f, (coil+rseries)*load*capacitance)
    return mechanical, electrical


def gas(f, rf, cf, ro, co):
    return lowpass(f, rf*cf) * lowpass(f, ro*co)


def settling(tau1, tau2, error=.01):
    """Unit-step settling for two cascaded real poles; excludes cells/ADC."""
    if min(tau1, tau2) <= 0 or not 0 < error < 1:
        raise ValueError('invalid settling parameters')
    def residual(t):
        if math.isclose(tau1, tau2):
            return (1+t/tau1)*math.exp(-t/tau1)
        return (tau1*math.exp(-t/tau1)-tau2*math.exp(-t/tau2))/(tau1-tau2)
    lo, hi = 0., 100*max(tau1, tau2)
    for _ in range(70):
        mid = (lo+hi)/2
        if residual(mid) > error: lo = mid
        else: hi = mid
    return hi


def value(text):
    text=text.removesuffix(' C0G')
    match = re.fullmatch(r'([0-9.]+)\s*(k|M|u|n|p)?(?:F|R|ohm)?', text)
    if not match: raise ValueError(f'unsupported component value: {text}')
    return float(match[1])*{None: 1, 'k': 1e3, 'M': 1e6, 'u': 1e-6, 'n': 1e-9, 'p': 1e-12}[match[2]]


def pcb_values(path):
    import pcbnew
    board = pcbnew.LoadBoard(str(path))
    return {f.GetReference(): f.GetValue() for f in board.GetFootprints()}


def build_report():
    from project_paths import board_dir
    header=(ROOT/'sw/skylark/firmware/skylark.h').read_text(encoding='utf-8')
    for key,expected in [('SK_GAS_SLOT_MS',60),('SK_ADC_CONFIG1',2)]:
        match=re.search(r'^#define '+key+r' (\w+)$',header,re.M)
        if not match or int(match[1],0)!=expected:
            raise ValueError(f'review response model for changed {key}')
    driver=ast.parse((ROOT/'sw/pi/groundlark/geophone.py').read_text(encoding='utf-8'))
    registers=next(ast.literal_eval(n.value) for n in ast.walk(driver) if isinstance(n,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=='REGISTERS' for t in n.targets))
    if registers != (0x0c,0x88,0x50,0):
        raise ValueError('review response model for changed Groundlark ADC profile')
    paths = [board_dir(name)/f'{name}.kicad_pcb' for name in ('groundlark-daqhat-01', 'skylark-usb')]
    g, k = (pcb_values(p) for p in paths)
    gv, kv = lambda ref: value(g[ref]), lambda ref: value(k[ref])
    rs, rb = gv('R90')+gv('R91'), gv('R92')+gv('R93')
    if gv('R90') != gv('R91') or gv('R92') != gv('R93') or gv('C91') != gv('C92'):
        raise ValueError('differential reduction requires a symmetric nominal input')
    cap = gv('C90') + gv('C91')/2
    geo = []
    rate = 1_024_000/3116  # TI table 12, continuous conversion (not nominal 330).
    for f, adc in ADC_PLOTS[330].items():
        m, e = geophone(f, rs, rb, cap)
        corners = [db(math.prod(geophone(f, rs*r, rb*b, cap*c, 395*w, f0, z)))
                   for r,b,c,w,f0,z in itertools.product((.99,1.01),(.99,1.01),(.95,1.05),
                                                       (.95,1.05),(4.,5.),(.63,.77))]
        geo.append(dict(hz=f, mechanical_db=db(m), circuit_db=db(e),
                        pre_adc_phase_deg=phase(m*e), adc_plot_db=adc,
                        combined_estimate_db=db(m*e)+adc,
                        pre_adc_corner_db=[min(corners),max(corners)],
                        recorded_alias_hz=folded(f,rate)))
    gas_rows = []
    for label, base, sens in [('SO2',30,.4e-6),('H2S',50,1.7e-6)]:
        poles = []
        for off, el in ((0,'WE'),(3,'AE')):
            cf = kv(f'C{base+off}')
            if label == 'H2S':
                cf += sum(kv(f'C{i}') for i in range(80 if off==0 else 84,84 if off==0 else 88))
            rf, ro, co = kv(f'R{base+off+1}'), kv(f'R{base+off+2}'), kv(f'C{base+off+1}')
            poles.append((rf*cf,ro*co))
            rows = []
            for f, adc in ADC_PLOTS[20].items():
                h = gas(f,rf,cf,ro,co)
                rows.append(dict(hz=f, circuit_db=db(h), circuit_phase_deg=phase(h),
                                 adc_plot_db=adc, combined_electronics_estimate_db=db(h)+adc,
                                 recorded_alias_hz=folded(f,1000/240)))
            gas_rows.append(dict(channel=f'{label}_{el}', poles_hz=[1/(2*math.pi*t) for t in poles[-1]],
                                 nominal_V_per_ppm=sens*rf, nominal_counts_per_ppb=sens*rf*2**23/2.5/1000,
                                 electronic_step_1percent_s=settling(*poles[-1]),
                                 rows=rows))
        if poles[0] != poles[1]: raise ValueError(f'{label} WE/AE nominal filter mismatch')
    paths += [ROOT/p for p in ('sw/pi/groundlark/sensors.py','sw/pi/groundlark/geophone.py',
                               'sw/skylark/firmware/sensors.c','sw/skylark/firmware/core.c',
                               'sw/skylark/firmware/skylark.h')]
    return dict(
        physical_qualification=False,
        sources=dict(adc=TI, imu=ST, so2=SGX+'DS-0685-SGX-7SO2-AQ-20.pdf', h2s=SGX+'DS-0681-SGX-7H2S-AQ-25.pdf'),
        source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        adc_plot_method='Approximate checkpoints digitized from SBAS751B figs 45/50; allow 0.5 dB reading uncertainty, not a device tolerance. No notch-depth or sub-resolution flatness claim.',
        groundlark=dict(geophone=geo, actual_nominal_rate_hz=rate,
                        clock_tolerance_rate_hz=[rate*.98,rate*1.02],
                        adc_bandwidth_hz=150.1, adc_conversion_window_s=3116/1_024_000,
                        adc_phase_deg=None, absolute_sensitivity_tolerance_fraction=.1,
                        imu_profiles=[dict(odr_hz=odr, acceleration_lpf1_hz=odr/2, gyro_lpf2_hz=bw)
                                      for odr,bw in ((26,8.3),(52,16.6),(104,33),(208,66.8))],
                        gyro_26hz_manufacturer_phase_point=dict(hz=2.5,phase_deg=-36,phase_delay_s=.04),
                        imu_phase_and_alias_rejection_qualified=False),
        skylark=dict(gas=gas_rows, per_channel_nominal_rate_hz=1000/240,
                     minimum_slot_s=.060, adc_single_shot_s=51213/1_024_000,
                     worst_slow_clock_single_shot_s=51213/(1_024_000*.98),
                     adc_bandwidth_hz=13.1, adc_phase_deg=None,
                     we_ae_equal_interference_residual=[dict(hz=f, fraction=2*abs(math.sin(math.pi*f*.06)))
                                                       for f in (.01,.1,1,4.1666667)],
                     gas_cell_t90_spec_s=60, gas_cell_transfer=None, enclosure_transfer=None,
                     illustrative_first_order_cells=[dict(assumed_t90_s=t90, hz=f,
                                                           db=db(lowpass(f,t90/math.log(10))),
                                                           phase_deg=phase(lowpass(f,t90/math.log(10))))
                                                     for t90 in (5,30,60) for f in (.01,.1,1)],
                     climate=dict(published_hz=1, heater=False, physical_response=None),
                     pressure=dict(internal_hz=3.125, published_hz=1, pressure_osr=8, temperature_osr=2,
                                   iir_coefficient=0, anti_alias_before_publication=False),
                     particles=dict(published_hz=1, maximum_frame_age_s=1.5, physical_response=None)),
        findings=[
            'Groundlark mechanical rolloff removes most sub-hertz velocity sensitivity; no inverse response is applied.',
            'Neither chain has demonstrated broadband alias rejection. ADC bandwidth alone is not a stopband specification.',
            'Skylark electronics pass near 4.17 Hz, which can alias into a slowly varying gas baseline. Cell response cannot suppress interference injected after the cell.',
            'Adjacent WE/AE observations are separated by at least 60 ms; direct subtraction is not simultaneous common-mode cancellation.',
            'BMP390 latest-sample publication at 1 Hz is unfiltered rate reduction; use as weather pressure, not an infrasound waveform.',
            'Published gas-cell T90 is an upper limit, not a guaranteed low-pass transfer function or power-up settling time.',
            'First-order gas examples are sensitivity scenarios only, not measured cells or bounds; hood transport adds an unknown delay.',
            'ADC FIR coefficients/group delay, IMU phase, op-amp/cell loop response and enclosure response need manufacturer data or physical measurements.',
        ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'hw/shared/simulation/signal-response/results.json')
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Response budget generated; physical qualification and alias rejection remain open.')


if __name__ == '__main__': main()
