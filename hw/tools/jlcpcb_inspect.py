"""Independently parse exported Gerber/Excellon and compare drills to KiCad.

Dependencies: pcbnew 9, gerbonara 1.5.0, rsvg-convert. Read-only on CAD.
"""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
import pcbnew as p
from gerbonara import GerberFile, ExcellonFile, LayerStack
from gerbonara.utils import MM
from jlcpcb_package import BOARD, ROOT, EXTENSIONS, write_json, validate_plot_inventory, check_drills, sha
from jlcpcb_quantity import check_single_outline


def drill_key(x, y, diameter):
    return tuple(float(v) for v in (x, y, diameter))


def inspect(out):
    plots = out / 'gerbers'; review = out / 'review'
    manifest = json.loads((out / 'manifest.json').read_text())
    for source, expected_hash in manifest['source_sha256'].items():
        if sha(ROOT / source) != expected_hash:
            raise ValueError(f'Source changed since export: {source}')
    validate_plot_inventory(plots)
    b = p.LoadBoard(str(BOARD))
    expected = {'PTH': Counter(), 'NPTH': Counter()}
    for f in b.GetFootprints():
        for pad in f.Pads():
            dx, dy = p.ToMM(pad.GetDrillSize())
            if not dx: continue
            if abs(dx - dy) > 1e-6: raise ValueError('Slot added: extend independent drill comparison')
            x, y = p.ToMM(pad.GetPosition())
            kind = 'NPTH' if pad.GetAttribute() == p.PAD_ATTRIB_NPTH else 'PTH'
            expected[kind][drill_key(x, -y, dx)] += 1
    for via in b.GetTracks():
        if not isinstance(via, p.PCB_VIA): continue
        kind = 'PTH'
        if via.GetViaType() != p.VIATYPE_THROUGH:
            raise ValueError('Non-through via in standard-process export')
        x, y = p.ToMM(via.GetPosition())
        expected[kind][drill_key(x, -y, p.ToMM(via.GetDrillValue()))] += 1
    result = {'parser': 'gerbonara 1.5.0', 'drill_coordinate_tolerance_mm': 0.001, 'drills': {}, 'layers': {}}
    for kind, want in expected.items():
        drill = ExcellonFile.open(plots / f'groundlark-daqhat-01-{kind}.drl')
        got = Counter(drill_key(o.x, o.y, o.tool.diameter) for o in drill.objects)
        check_drills(list(want.elements()), list(got.elements()))
        result['drills'][kind] = sum(got.values())
    for path in sorted(plots.iterdir()):
        if path.suffix[1:] not in EXTENSIONS: continue
        layer = GerberFile.open(path)
        if not layer.objects: raise ValueError(f'Empty plot: {path.name}')
        if path.suffix == '.gm1':
            from gerbonara.graphic_objects import Line
            if any(not isinstance(o, Line) or not o.polarity_dark or o.unit != MM for o in layer.objects):
                raise ValueError('Expected millimetre dark-line board outline only')
            result['single_board_outline'] = check_single_outline([
                ((o.x1, o.y1), (o.x2, o.y2)) for o in layer.objects])
        result['layers'][path.name] = {'objects': len(layer.objects), 'bounds_mm': layer.bounding_box(unit=MM)}
    stack = LayerStack.open(plots)
    for side in ('top', 'bottom'):
        # Plain SVG avoids filter effects unsupported by CairoSVG. Include
        # copper, legend and outline, but not opaque mask/paste overlays.
        svg = str(stack.to_svg(side_re=f'{side}|mechanical', margin=1,
                               force_bounds=((50, -106), (190, -50)),
                               colors={f'{side} copper': '#417e87', f'{side} silk': '#111111',
                                       'mechanical outline': '#222222', 'drill pth': '#ffffff',
                                       'drill npth': '#ffffff', 'drill unknown': '#ffffff'}))
        # Gerbonara emits silk before copper. Draw it above copper in this
        # review composite so artwork over masked copper remains visible.
        root = ET.fromstring(svg)
        silk = next(g for g in root if g.get('id') == f'l-{side}-silk')
        copper = next(g for g in root if g.get('id') == f'l-{side}-copper')
        root.remove(silk)
        # Clear-polarity silk apertures remove ink, not underlying copper.
        # Represent the layer as a luminance mask rather than white overpaint.
        ns = '{http://www.w3.org/2000/svg}'
        mask = ET.Element(ns + 'mask', {'id': f'{side}-ink', 'maskUnits': 'userSpaceOnUse',
                                        'x': '49', 'y': '-107', 'width': '142', 'height': '58'})
        for node in silk.iter():
            for attr in ('fill', 'stroke'):
                value = node.get(attr)
                if value and value != 'none':
                    node.set(attr, '#000000' if value.lower() in ('white', '#fff', '#ffffff') else '#ffffff')
        mask.append(silk)
        definitions = ET.Element(ns + 'defs'); definitions.append(mask)
        root.insert(0, definitions)
        ink = ET.Element(ns + 'rect', {'x': '49', 'y': '-107', 'width': '142', 'height': '58',
                                       'fill': '#111111', 'mask': f'url(#{side}-ink)'})
        root.insert(list(root).index(copper) + 1, ink)
        if side == 'bottom':
            group = ET.Element('{http://www.w3.org/2000/svg}g', {'transform': 'translate(240 0) scale(-1 1)'})
            for child in list(root): root.remove(child); group.append(child)
            root.append(group)
        svg = ET.tostring(root, encoding='unicode')
        (review / f'gerber-{side}.svg').write_text(svg, encoding='utf-8')
        subprocess.run(['rsvg-convert', '-w', '1600', '-b', 'white', '-o',
                        str(review / f'gerber-{side}.png'), str(review / f'gerber-{side}.svg')], check=True)
    write_json(review / 'independent-check.json', result)
    print(json.dumps({'drills': result['drills'], 'parsed_layers': len(result['layers'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    inspect(parser.parse_args().package)
