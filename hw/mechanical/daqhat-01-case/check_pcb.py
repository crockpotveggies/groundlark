"""Read-only native KiCad checks for the R3 enclosure's underside ledges.

Run with KiCad's Python environment. Includes an in-memory collision fault;
never saves or changes the board.
"""
import hashlib
import json
from pathlib import Path
import pcbnew as p

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT/'hw/groundlark-fpga-hat/boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb'
LEDGES = [(104, 0, 110, 4), (104, 52, 110, 56), (134, 0, 140, 4), (134, 52, 140, 56)]


def bounds(item):
    b = item.GetBoundingBox(False, False) if isinstance(item, p.FOOTPRINT) else item.GetBoundingBox()
    return (p.ToMM(b.GetLeft())-50, p.ToMM(b.GetTop())-50,
            p.ToMM(b.GetRight())-50, p.ToMM(b.GetBottom())-50)


def verify(board):
    checked = 0
    for fp in board.GetFootprints():
        obstacles = [(fp.GetReference(), bounds(fp))] if fp.IsFlipped() else []
        obstacles += [(fp.GetReference()+'.'+pad.GetNumber(), bounds(pad))
                      for pad in fp.Pads() if pad.GetDrillSize().x]
        for name, b in obstacles:
            for a in LEDGES:
                # 0.5 mm lateral allowance around underside bodies and tails.
                gap = max(a[0]-b[2], b[0]-a[2], a[1]-b[3], b[1]-a[3])
                assert gap > .5, f'Power ledge underside collision: {name}'
                checked += 1
    return checked


def main():
    board = p.LoadBoard(str(BOARD))
    checked = verify(board)
    jack = next(f for f in board.GetFootprints() if f.GetReference() == 'J83')
    assert jack.GetOrientationDegrees() % 360 == 180
    assert abs(p.ToMM(jack.GetPosition().x)-145) < .001
    assert abs(p.ToMM(jack.GetPosition().y)-64.1) < .001
    pad = next(q for q in jack.Pads() if q.GetNumber() == '1')
    pad.SetPosition(p.VECTOR2I(p.FromMM(157), p.FromMM(52)))
    try:
        verify(board)
    except AssertionError as error:
        assert 'J83.1' in str(error)
    else:
        raise AssertionError('Injected tail collision was not detected')
    report = dict(underside_checks=checked,clearance_allowance_mm=.5,
                  injected_collision_rejected=True,
                  board_sha256=hashlib.sha256(BOARD.read_bytes()).hexdigest(),
                  check_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='Native underside footprint and drilled-pad bounds; printed height and retention unqualified.')
    out = ROOT/'hw/releases/groundlark-case-r3/evidence/native-pcb-fit.json'
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
