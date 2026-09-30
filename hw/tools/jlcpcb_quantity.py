"""Fail closed on batch quantities, duplicated outlines or multiplied BOM totals."""
import csv
import json
from jlcpcb_bom import require_single_hat


def check_single_outline(segments):
    """Independent expected profile: four sides of one 140 x 56 mm HAT."""
    corners = [(50, -50), (190, -50), (190, -106), (50, -106)]
    edge = lambda a, b: tuple(sorted((tuple(a), tuple(b))))
    expected = {edge(corners[i], corners[(i+1) % 4]) for i in range(4)}
    actual = [edge(a, b) for a, b in segments]
    if len(actual) != 4 or set(actual) != expected:
        raise ValueError('Expected exactly one unpanelized 140 x 56 mm rectangular HAT outline')
    return {'closed_board_outlines': 1, 'boards_per_design': 1, 'panelized': False,
            'board_mm': [140, 56]}


def audit_quantity(out):
    manifest = json.loads((out/'manifest.json').read_text())
    for key in ['requested_assembled_HATs', 'requested_fabricated_HATs', 'boards_per_gerber_design']:
        require_single_hat(manifest[key])
    if manifest['panelized'] is not False:
        raise ValueError('Panelized assembly is not authorized')
    def rows(name):
        with (out/name).open(newline='', encoding='utf-8') as stream:
            return list(csv.DictReader(stream))
    bom, cpl, procurement = [rows(name) for name in ['BOM-review.csv', 'CPL-review.csv', 'procurement.csv']]
    refs = [ref for row in bom for ref in row['Designator'].split(',')]
    placements = [row['Designator'] for row in cpl]
    purchased = [ref for row in procurement for ref in row['Designator'].split(',')]
    for candidates in [refs, placements, purchased]:
        if len(candidates) != len(set(candidates)) or set(candidates) != set(refs):
            raise ValueError('BOM/CPL/procurement references must agree, exactly once per HAT')
    if len(refs) != manifest['counts']['physical_placements']:
        raise ValueError('Placement count differs from manifest')
    for row in procurement:
        count = len(row['Designator'].split(','))
        if (row['Requested_HATs'], row['Per_HAT'], row['Installed_total']) != ('1', str(count), str(count)):
            raise ValueError('Procurement quantities must describe exactly one HAT')
    outline = json.loads((out/'review/independent-check.json').read_text())['single_board_outline']
    if outline != check_single_outline([((50,-50),(190,-50)), ((190,-50),(190,-106)),
                                       ((190,-106),(50,-106)), ((50,-106),(50,-50))]):
        raise ValueError('Missing independent single-board outline evidence')
    return dict(requested_fabricated_HATs=1, requested_assembled_HATs=1,
                **outline, BOM_lines=len(bom), installed_components=len(refs),
                placement_rows=len(placements),
                order_note='Website quantities must both be 1. Files cannot override supplier order settings.')
