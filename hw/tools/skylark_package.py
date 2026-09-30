"""Read-only Skylark manufacturing review export; never authorizes an order."""
import argparse
import csv
import json
import re
import zipfile
from pathlib import Path

from jlcpcb_package import sha, run, write_json, write_csv, natural, check_reference_sets
from jlcpcb_placement import correct_placements
from skylark_fabrication import review, stackup

ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = ROOT / 'hw/skylark-usb/boards/skylark-usb'
BOARD = BOARD_DIR / 'skylark-usb.kicad_pcb'
ASSEMBLY = ROOT / 'hw/assembly/skylark-usb'
REGISTRY = ASSEMBLY / 'jlcpcb-parts.json'
MAPPINGS = ASSEMBLY / 'jlcpcb-placement.json'
LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu', 'F.Paste', 'B.Paste',
          'F.SilkS', 'B.SilkS', 'F.Mask', 'B.Mask', 'Edge.Cuts']


def assembled(ref):
    return bool(re.fullmatch(r'[A-Z]+[0-9]+', ref)) and not ref.startswith(('GS', 'TP', 'H'))


def select(source, registry):
    """Require exact coverage and bind every override to its authored identity."""
    lookup = {}
    for part in registry['parts']:
        for ref in part['references']:
            if ref in lookup:
                raise ValueError(f'Duplicate procurement reference: {ref}')
            lookup[ref] = part
        for key in ('manufacturer', 'mpn', 'source_mpn', 'jlcpcb_part', 'manufacturer_evidence', 'source_url', 'observation_date_utc'):
            if not part.get(key):
                raise ValueError(f'Missing procurement identity/evidence: {key}')
        if (part.get('ordering_status') != 'available'
                or part.get('minimum_order_quantity') != 1
                or not isinstance(part.get('available_order_quantity'), int)
                or part['available_order_quantity'] < len(part['references'])
                or not isinstance(part.get('stock'), int) or part['stock'] <= 0):
            raise ValueError(f'Procurement policy: stocked, no preorder, minimum one required: {part["mpn"]}')
    rows = {r['Reference']: r for r in source if assembled(r['Reference'])}
    if len(rows) != sum(assembled(r['Reference']) for r in source) or set(rows) != set(lookup):
        raise ValueError('Incomplete or duplicate assembly BOM coverage')
    for ref, row in rows.items():
        part = lookup[ref]
        if row['MPN'] != part['source_mpn'] or row['Footprint'] not in part['source_footprints']:
            raise ValueError(f'Stale procurement binding: {ref}')
        if row['DNP'] != 'False':
            raise ValueError(f'Unreviewed DNP variant: {ref}')
        if part['mpn'] != part['source_mpn'] and not part.get('resolution'):
            raise ValueError(f'Undocumented substitution: {ref}')
    return lookup


def placement_inputs(board, selections):
    import pcbnew as p
    placements, geometry, selected = [], [], {}
    for f in sorted(board.GetFootprints(), key=lambda x: natural(x.GetReference())):
        ref = f.GetReference()
        if ref not in selections:
            continue
        part = selections[ref]
        x, y = p.ToMM(f.GetPosition())
        side = 'Bottom' if f.IsFlipped() else 'Top'
        placements.append(dict(Designator=ref, MidX=f'{x:.6f}mm', MidY=f'{-y:.6f}mm', Layer=side, Rotation=f'{f.GetOrientationDegrees()%360:.6f}'))
        geometry.append(dict(reference=ref, side=side, footprint_origin_mm=[x, y], rotation_deg=f.GetOrientationDegrees()%360,
            pads=[dict(number=a.GetNumber(), xy_mm=list(p.ToMM(a.GetPosition())), size_mm=list(p.ToMM(a.GetSize())), rotation_deg=a.GetOrientationDegrees()) for a in f.Pads() if a.GetNumber()]))
        selected[ref] = dict(mpn=part['mpn'], lcsc=part['jlcpcb_part'], source_footprint=part['native_footprint'])
    if set(selected) != set(selections):
        raise ValueError('PCB missing selected assembly component')
    return placements, geometry, selected


def export(out):
    import pcbnew as p
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be new or empty')
    paths = [BOARD, BOARD.with_suffix('.kicad_pro'), BOARD_DIR/'bom.csv', REGISTRY, MAPPINGS,
             ASSEMBLY/'sensor-requirements.json', ROOT/'hw/skylark-usb/elec/skylark.ato',
             ROOT/'hw/shared/elec/skylark/parts.ato', ROOT/'hw/skylark-usb/layout/placement.json']
    before = {f.relative_to(ROOT).as_posix(): sha(f) for f in paths}
    b = p.LoadBoard(str(BOARD))
    construction = dict(**stackup(BOARD.read_text()), **review(b))
    with (BOARD_DIR/'bom.csv').open(encoding='utf-8', newline='') as stream:
        source = list(csv.DictReader(stream))
    refs = {f.GetReference(): f for f in b.GetFootprints()}
    native = [r for r in source if re.fullmatch(r'[A-Z]+[0-9]+', r['Reference'])]
    if len(native) != len(refs) or {r['Reference'] for r in native} != set(refs):
        raise ValueError('PCB/BOM reference mismatch')
    registry = json.loads(REGISTRY.read_text())
    selections = select(source, registry)
    selections = {r['Reference']: dict(selections[r['Reference']], native_footprint=r['Footprint']) for r in source if assembled(r['Reference'])}
    placements, geometry, selected = placement_inputs(b, selections)
    placements, audit = correct_placements(placements, geometry, selected, json.loads(MAPPINGS.read_text()))
    bom = [dict(Comment=part['mpn'], Designator=','.join(sorted(part['references'], key=natural)),
                Footprint=part['specification'], **{'LCSC Part #': part['jlcpcb_part']}) for part in registry['parts']]
    check_reference_sets(bom, placements)
    out.mkdir(parents=True, exist_ok=True)
    evidence = out/'review'; evidence.mkdir()
    plots = out/'gerbers'; plots.mkdir()
    run('kicad-cli', 'pcb', 'drc', BOARD, '--format', 'json', '--severity-all', '--exit-code-violations', '-o', evidence/'drc.json')
    drc = json.loads((evidence/'drc.json').read_text())
    if any(drc.get(k) for k in ('violations', 'unconnected_items', 'schematic_parity')):
        raise ValueError('Native DRC failed')
    run('kicad-cli', 'pcb', 'export', 'gerbers', BOARD, '-o', str(plots)+'/', '-l', ','.join(LAYERS), '--subtract-soldermask', '--precision', '6')
    run('kicad-cli', 'pcb', 'export', 'drill', BOARD, '-o', str(plots)+'/', '--format', 'excellon',
        '--drill-origin', 'absolute', '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
        '--excellon-oval-format', 'route', '--excellon-separate-th', '--generate-report', '--report-path', evidence/'drill-report.txt')
    extensions = {'gtl','g1','g2','gbl','gtp','gbp','gto','gbo','gts','gbs','gm1','drl','gbrjob'}
    if {f.suffix[1:] for f in plots.iterdir()} != extensions:
        raise ValueError('Unexpected or missing manufacturing layers')
    drills = list(plots.glob('*.drl'))
    if len(drills) != 2 or not all(any(tag in f.read_text() for f in drills) for tag in ('NonPlated,1,4,NPTH','Plated,1,4,PTH')):
        raise ValueError('Expected separate four-layer through-hole drill files')
    for side, layers in [('top','F.Fab,F.SilkS,Edge.Cuts'),('bottom','B.Fab,B.SilkS,Edge.Cuts')]:
        run('kicad-cli','pcb','export','svg',BOARD,'-o',evidence/f'assembly-{side}.svg','-l',layers,'--mode-single',
            '--fit-page-to-board','--exclude-drawing-sheet','--sketch-pads-on-fab-layers',*(['--mirror'] if side=='bottom' else []))
    write_csv(out/'BOM-review.csv', list(bom[0]), bom)
    write_csv(out/'CPL-review.csv', list(placements[0]), placements)
    write_json(evidence/'supplier-placement-audit.json', audit)
    write_json(evidence/'supplier-placement-mappings.json', json.loads(MAPPINGS.read_text()))
    write_json(evidence/'sensor-requirements.json', json.loads((ASSEMBLY/'sensor-requirements.json').read_text()))
    write_json(evidence/'placement-geometry.json', geometry)
    write_json(evidence/'procurement.json', registry)
    write_json(evidence/'manual-parts.json', registry['manual_parts'])
    write_json(evidence/'construction.json', construction)
    holds = [f"{','.join(part['references'])}: {part['mpn']} {part['ordering_status']}" for part in registry['parts'] if part['ordering_status'] != 'available']
    holds += [a['reference']+': '+a['status'] for a in audit if 'pads_checked' not in a]
    holds += ['Exact AQ-cell bias needs SGX confirmation; operation below 800 mbar unqualified.',
              'Review both sides in JLCPCB order preview, including pin 1, USB slots and THT header.',
              'Manual sockets/cells/harness and physical electrical/mechanical qualification pending.',
              'User owns fabrication approval. Inventory observations are dated, not reservations.']
    with zipfile.ZipFile(out/'Skylark-Gerbers-REVIEW.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for f in sorted(plots.iterdir()): archive.write(f,f.name)
    if before != {f.relative_to(ROOT).as_posix(): sha(f) for f in paths}:
        raise ValueError('Source changed during read-only export')
    manifest = dict(status='ENGINEERING REVIEW ONLY; NOT RELEASED', source_sha256=before,
        kicad=run('kicad-cli','version'), board_mm=[90,100], construction=construction,
        copper_layers=LAYERS[:4], physical_placements=len(placements), bom_lines=len(bom),
        supplier_fitted_placements=sum('pads_checked' in a for a in audit), holds=holds,
        files_sha256={f.relative_to(out).as_posix():sha(f) for f in sorted(out.rglob('*')) if f.is_file()})
    write_json(out/'manifest.json',manifest)
    (out/'READ-ME-FIRST.txt').write_text('ENGINEERING REVIEW ONLY; NOT RELEASED\n\n'
        '90 x 100 mm, 4-layer stock FR-4 JLC04161H-7628, 1.6 mm, outer 1 oz / inner 0.5 oz.\n'
        'Through-vias only; no filled/capped vias, via-in-pad, blind vias or custom lamination.\n'
        'CPL coordinates: mm, absolute board X and negated board Y; bottom shown from top.\n'
        'Do not mirror absolute CPL coordinates. Assembly SVG bottom view is mirrored for inspection.\n\n'
        +'\n'.join(holds)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(export(parser.parse_args().out),indent=2))
