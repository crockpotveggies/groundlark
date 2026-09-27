"""Publish the checked artifact state, with hashes and explicit model limits."""
from pathlib import Path
from project_paths import board_dir, placement_path
import json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[2]
rows=[]
for name in ['groundlark-hat','groundlark-field-head']:
    r=json.loads((board_dir(name)/'validation.json').read_text())
    assert not r['connectivity_errors'] and not r['drc_errors'] and not r['erc_findings'] and not r['unconnected_items'],r
    warnings=sum(r['drc_findings_by_type'].values())
    rows.append(f"| {name} | {r['atopile_pin_checks']} | {r['erc_findings']} | {r['drc_errors']} | {warnings} | {r['unconnected_items']} | {r['tracks_and_vias']} |")
sim=json.loads((ROOT/'hw/shared/simulation/results.json').read_text());assert len(sim['cases'])==27 and all(not x['failures'] for x in sim['cases'])
cir=json.loads((ROOT/'hw/shared/simulation/circuit-checks.json').read_text());assert all(x['circuit_invariants']=='PASS' for x in cir['boards'])
pos=(ROOT/'hw/logs/constraint-solve.log').read_text();neg=(ROOT/'hw/logs/negative-voltage.log').read_text()
assert 'PASS: explicit upstream constraint solve hat' in pos and 'PASS: explicit upstream constraint solve field_head' in pos
assert 'PASS: upstream solver rejected 5V' in neg
files=list((ROOT/'hw/shared/elec').glob('*.ato'))+[ROOT/'hw/ato.yaml',placement_path('groundlark-hat'),placement_path('groundlark-field-head'),ROOT/'hw/groundlark-coldfoot-hat/layout/fixed-routes.json']
for product in ('groundlark-coldfoot-hat', 'burrowlark-usb'):
    files.extend((ROOT/'hw'/product/'elec').glob('*.ato'))
files.extend((ROOT/'hw/tools').glob('*.py'))
files.extend((ROOT/'hw/shared/simulation').glob('*.cir'))
for name in ['groundlark-hat','groundlark-field-head']:
    folder=board_dir(name)
    files.extend([folder/(name+'.kicad_pcb'),folder/(name+'.kicad_pro'),folder/(name+'.ses'),*folder.glob('*.kicad_sch'),folder/'drc.json',folder/'erc.json',folder/'validation.json',folder/'bom.csv'])
files.extend([ROOT/'hw/shared/simulation/results.json',ROOT/'hw/shared/simulation/circuit-checks.json'])
manifest={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(ROOT/'docs/artifact-manifest.json').write_text(json.dumps(manifest,indent=2))
text='''# A2 validation and release gates

**Engineering prototype — not released for fabrication or assembly.** The
circuit is authored in atopile; the native KiCad layout and review schematic
are derived from its compiled pins. Coldfoot silicon was not changed.

A2 puts USB-C only on the remote sensor head and removes the HAT cable interface.
The USB head requires firmware before it can enumerate. See [its circuit and
firmware contract](usb-sensor-head.md). USB connector mechanical holes are marked
on all copper layers in the local footprint, matching KiCad's multilayer PCB
representation; their drill dimensions and positions are unchanged.

## Recorded checks

Environment: atopile 0.15.9/Python 3.14.7, KiCad/pcbnew 9.0.9, ngspice 42,
Freerouting 1.9.0, WSL Ubuntu 24.04. The HAT has six copper layers (In1/In4 GND);
the field head has four (In1/In2 GND). Provisional minimum track/clearance is
0.15 mm, through-via diameter/drill 0.6/0.3 mm, copper-edge clearance 0.3 mm.
These rules are not a selected manufacturer's stackup or acceptance criteria.

| Board | Atopile pins compared | ERC findings | DRC errors | DRC warnings | Unconnected | Tracks/vias |
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'''

Evidence: each board's `validation.json`, `drc.json`, `erc.json` and exported
`schematic-netlist.xml` under each product's `boards/`. `hw/tools/check_design.py` checks source,
schematic and PCB pin agreement, independent Pi header corner coordinates and
the actual KiCad ERC/DRC engines. Library keepouts omitted during atopile board
conversion are restored before layout checks. No DRC violations are excluded.

- Explicit upstream atopile numeric solver: HAT and field-head rail/component
  constraints pass. The negative 5 V-to-3.6 V IMU case is correctly rejected.
- `hw/tools/check_circuit.py`: compiled pin assignments, source/BOM agreement,
  module bond/connector mapping, supply/clock/reset/UART direction and bypass
  invariants pass. Removed supervisor bypass and incorrect UART supply mutations
  are rejected.
- **27 ngspice cases pass**: rail/load/USB cable corners, I2C rise time, UART RC,
  USB CC resistor corners, ideal buck power stage and behavioral reset.
  See [simulation scope](../hw/shared/simulation/README.md) and the actual decks/logs.
- Native KiCad schematics, assembly previews and 3D renders were visually
  inspected. Custom module/socket bodies are simplified dimensioned envelopes.
- [Artifact hashes](artifact-manifest.json) identify the checked sources and CAD.

The SPICE cases do not simulate MEMS internals, geomagnetic sensitivity,
Coldfoot RTL, vendor regulator control loops or extracted PCB parasitics.
Pin agreement establishes CAD consistency; it does not replace independent
supplier pinout/package review. No firmware, inference, silicon, CDC, EMC,
signal-integrity, magnetic-noise or physical bench qualification is claimed.

## Before fabrication

1. Independently review the run-1 bond map, mating connector orientation,
   current per contact, exact package revisions and ordered parts. Confirm the
   optional DLVR suffix. The selected run-1 module replaces the earlier run-2
   incompatibility; its complete support circuit is now present.
2. Select a fabrication stackup and review routing: power drops/neck-downs,
   decoupling and buck switching loops, copper thermal paths, via return paths,
   USB data pair geometry and GNSS RF impedance. Clean DRC is not SI/PI signoff.
3. Verify Pi model, underside socket, cooler/ports/ribbon cable clearance,
   overhang support and run-1 stack height. The 120 × 56 mm carrier extends
   beyond the normal HAT outline; no HAT+ compliance certification is claimed.
4. Confirm the assumed 200 mA sensor and 600 mA Coldfoot envelopes, capacitor
   DC-bias derating, standby/partial-power behavior and ISO1640 input-low margin.
5. Implement/test USB enumeration, current limits, suspend/resume, timestamped
   sensor transport, EEPROM contents, overlays, acquisition/timestamping and
   the existing Coldfoot runtime integration before system performance claims.
6. Export and independently inspect manufacturing outputs after these reviews.
   No fabrication or assembly order has been placed.

## Bench acceptance

| Area | Required evidence |
|---|---|
| Power | Current-limited startup, regulator stability and transient droop, reset/brownout and all Pi power states |
| Timing/links | Sensor IDs, CRC/FIFO behavior, SPI modes, USB enumeration/suspend and local I2C timing, PPS timestamp uncertainty and 2 Mbaud runtime round trips |
| Motion/level | Axis orientation, known-angle calibration, stationary noise, thermal drift and correlated noise across four IMUs |
| Magnetics | Remote installation offsets, orientation, hard/soft-iron calibration and noise with Pi/fan/Coldfoot active; reference-station comparison |
| Infrasound option | Pressure calibration, noise, reference-volume/leak transfer function, wind response and saturation recovery |
| Coldfoot | Measured rail/contact currents and clocks, then deterministic recorded-input comparisons through its existing runtime |

The remote magnetometer needs its own orientation calibration; the HAT's
inclinometer does not automatically compensate a separately mounted head.
Aurora-related magnetic measurements are not optical aurora detection.
Add acquisition/replay fault-injection tests when firmware is introduced.
'''
(ROOT/'docs/validation.md').write_text(text)
print('Published validation and artifact hashes')
