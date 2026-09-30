"""Read actual KiCad geometry before quoting conventional six-layer fabrication.

This is a process-feature gate, not a replacement for DRC, electrical checks,
or a supplier quote. It never modifies the PCB or guesses a dollar price.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path


def standard_process_issues(features):
    issues = []
    if features['copper_layers'] != 6:
        issues.append('Expected six copper layers')
    expected=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
    if features.get('stack_copper_layers') != expected:
        issues.append('Serialized stack disagrees with the six-layer process')
    if set(features['tracks_by_layer'])-set(expected):
        issues.append('Copper exists on a disabled layer')
    if abs(features['thickness_mm'] - 1.6) > .001:
        issues.append('Expected 1.6 mm board thickness')
    if any(abs(a-b) > .1 for a, b in zip(features['size_mm'], [140, 56])):
        issues.append('Expected 140 x 56 mm outline with dedicated power section')
    if {name for name in features['ground_planes'] if name.startswith('In')} != {'In1.Cu', 'In4.Cu'}:
        issues.append('Expected two ground reference planes on L2 and L5')
    for via in features['vias']:
        if via['type'] != 'through' or via['span'] != ['F.Cu', 'B.Cu']:
            issues.append('Blind, buried or microvia requires a different fabrication process')
        if via['drill_mm'] < .3 - 1e-6:
            issues.append('Via drill below the 0.3 mm standard-price target')
        if via['pad_mm'] < .45 - 1e-6 or (via['pad_mm']-via['drill_mm'])/2 < .075-1e-6:
            issues.append('Via pad/annular ring below the selected POFV profile')
    if not features['vias']:
        issues.append('Missing via inventory')
    return sorted(set(issues))


def inspect(path):
    import pcbnew as p
    path = Path(path)
    board = p.LoadBoard(str(path))
    box = board.GetBoardEdgesBoundingBox()
    from stackup import block_span
    source=path.read_text();a,z=block_span(source,'(stackup')
    stack_layers=re.findall(r'\(layer\s+"([^"]+)"\s+\(type\s+"copper"\)',source[a:z])
    vias = []
    tracks = Counter()
    for item in board.GetTracks():
        if isinstance(item, p.PCB_VIA):
            kind = ('through' if item.GetViaType() == p.VIATYPE_THROUGH else
                    'microvia' if item.GetViaType() == p.VIATYPE_MICROVIA else 'blind/buried')
            vias.append(dict(type=kind, span=[board.GetLayerName(item.TopLayer()),
                                             board.GetLayerName(item.BottomLayer())],
                             drill_mm=p.ToMM(item.GetDrillValue()),
                             pad_mm=p.ToMM(item.GetWidth(item.TopLayer()))))
        else:
            tracks[board.GetLayerName(item.GetLayer())] += 1
    features = dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    copper_layers=board.GetCopperLayerCount(),
                    stack_copper_layers=stack_layers,
                    thickness_mm=p.ToMM(board.GetDesignSettings().GetBoardThickness()),
                    size_mm=[p.ToMM(box.GetWidth()), p.ToMM(box.GetHeight())],
                    ground_planes=sorted({board.GetLayerName(z.GetLayer()) for z in board.Zones()
                                         if not z.GetIsRuleArea() and z.GetNetname() == 'GND'}),
                    tracks_by_layer=dict(tracks), vias=vias)
    features['standard_process_issues'] = standard_process_issues(features)
    features['scope'] = 'Geometry/process screen only; DRC, circuit/fit checks and supplier review are separate'
    return features


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-standard', action='store_true')
    args = parser.parse_args()
    result = inspect(args.board)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k != 'vias'}, indent=2))
    print('Vias:', len(result['vias']))
    if args.require_standard and result['standard_process_issues']:
        raise SystemExit('PCB does not match the standard-price fabrication profile')
