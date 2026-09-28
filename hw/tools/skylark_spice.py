"""Optional OPAx387 vendor-model loop sensitivity sweeps, using native PCB values.

Supply TI's unmodified SBOMBI9B/OPAx387.LIB with --model. The model is not
redistributed. Cell/load impedances below are exploratory assumptions, NOT SGX
specifications. This never establishes physical stability or a noise floor.
"""
import argparse
import cmath
import hashlib
import json
import math
import re
from pathlib import Path
import subprocess
from signal_response import pcb_values,value
from project_paths import ROOT,board_dir


def phase_margin(rows):
    """All downward 0 dB crossings; interpolate in log frequency."""
    crossings=[];previous_phase=None;unwrapped=[]
    for frequency,loop in rows:
        phase=math.degrees(cmath.phase(loop))
        if previous_phase is not None:
            while phase-previous_phase>180:phase-=360
            while phase-previous_phase< -180:phase+=360
        previous_phase=phase;unwrapped.append((frequency,abs(loop),phase))
    for a,b in zip(unwrapped,unwrapped[1:]):
        if a[1]>=1>b[1]:
            fraction=math.log(a[1])/(math.log(a[1])-math.log(b[1]))
            crossings.append(dict(hz=a[0]*(b[0]/a[0])**fraction,
                                  phase_margin_deg=180+a[2]+(b[2]-a[2])*fraction))
    if not crossings:raise ValueError('No unity-gain crossing in model sweep')
    return crossings


def cases(parts):
    v=lambda ref:value(parts[ref])
    rows=[]
    for supply in (3.05,3.366):
        for direct_pf in (50,200,500):
            for guard_nf in (1,10):
                rows.append((f'buffer_{supply}_{direct_pf}_{guard_nf}',dict(
                    kind='VZERO buffer',supply_V=supply,direct_load_pF=direct_pf,guard_load_nF=guard_nf),
                    f'Xamp mid inv vcc 0 out OPAx387\nRfb out feedback 1u\nCdirect out 0 {direct_pf}p\n'
                    f'Rguard out guard {v("R75")}\nCguard guard 0 {guard_nf}n'))
        for base,gas in ((30,'SO2'),(50,'H2S')):
            caps=[f'C{base}']+([f'C{i}' for i in range(80,84)] if base==50 else [])
            for cell_c in (1e-9,1e-6,1e-3):
                for cell_r in (1e3,1e6):
                    rows.append((f'tia_{gas}_{supply}_{cell_c}_{cell_r}',dict(
                        kind='TIA',gas=gas,supply_V=supply,assumed_cell_F=cell_c,assumed_cell_ohm=cell_r),
                        f'Xamp mid inv vcc 0 out OPAx387\nRf out feedback {v(f"R{base+1}")}\n'
                        f'Cf out feedback {sum(v(c) for c in caps)}\nRload feedback cell {v(f"R{base}")}\n'
                        f'Ccell cell mid {cell_c}\nRcell cell mid {cell_r}\n'
                        f'Ro out adc {v(f"R{base+2}")}\nCo adc 0 {v(f"C{base+1}")}'))
    return rows


def run(model,out):
    board=board_dir('skylark-usb')/'skylark-usb.kicad_pcb'
    parts=pcb_values(board);out.mkdir(parents=True,exist_ok=True)
    # ngspice applies PSpice parsing before reading the untouched TI library.
    (out/'.spiceinit').write_text('set ngbehavior=ps\n',encoding='ascii')
    results=[]
    for name,assumptions,network in cases(parts):
        path=out/(name+'.cir');data=out/(name+'.txt')
        path.write_text(f'Skylark optional vendor-model scenario {name}\n'
            f'.include "{model.resolve()}"\nVcc vcc 0 {assumptions["supply_V"]}\nVmid mid 0 1.25\n'
            'Vinject inv feedback DC 0 AC 1\n'+network+'\n'
            '.control\nop\nprint v(out)\nset wr_singlescale\nset wr_vecnames\nac dec 100 1 1e9\n'
            'let loop=-v(feedback)/v(inv)\n'
            f'wrdata {data.name} loop\nquit\n.endc\n.end\n',encoding='utf-8')
        p=subprocess.run(['ngspice','-b',path.name],cwd=out,capture_output=True,text=True,timeout=60)
        (out/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode or not data.exists():raise RuntimeError(f'{name}: ngspice failed; inspect retained log')
        dc=re.search(r'v\(out\)\s*=\s*([-+0-9.eE]+)',p.stdout)
        if not dc or abs(float(dc[1])-1.25)>.01:
            raise ValueError(f'{name}: invalid DC bias; do not interpret AC margin')
        rows=[]
        for line in data.read_text().splitlines()[1:]:
            f,real,imag=map(float,line.split());rows.append((f,complex(real,imag)))
        crossings=phase_margin(rows)
        results.append(dict(name=name,**assumptions,crossings=crossings,
            minimum_phase_margin_deg=min(c['phase_margin_deg'] for c in crossings),
            below_45_degree_investigation_threshold=any(c['phase_margin_deg']<45 for c in crossings)))
    report=dict(physical_qualification=False,model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
        model_source='https://www.ti.com/lit/zip/SBOMBI9',
        pcb_sha256=hashlib.sha256(board.read_bytes()).hexdigest(),cases=results,
        scope='AC voltage-injection loop sweeps of reference buffer and each gas TIA; unmeasured lumped loads, typical vendor model, no temperature/process guarantees.',
        exclusions=['CE/RE electrochemical loop needs actual cell impedance/model.',
                    'Startup, saturation recovery, power-off backfeed, layout parasitics and noise are not qualified.',
                    'A 45-degree model margin is an investigation threshold, not fabrication approval.'])
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'{len(results)} model scenarios; minimum margin {min(r["minimum_phase_margin_deg"] for r in results):.1f} degrees (assumed loads).')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'hw/shared/simulation/ic-review')
    args=parser.parse_args();run(args.model,args.output.resolve())
