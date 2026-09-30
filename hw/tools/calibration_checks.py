"""Independent passive probe-access checks; no physical calibration claim."""
import math

# Deliberately separate from placement/atopile metadata and PCB net numbering.
PROBES = {'TP90': ('GND', 'C93', '2'), 'TP91': ('GEO_VCM', 'C93', '1'),
          'TP92': ('GEO_AVDD', 'C94', '1'), 'TP93': ('GEO_DRDY_N', 'R97', '1')}


def verify(rows):
    if set(rows) != set(PROBES): raise ValueError('calibration probe inventory')
    for ref, (net, _, _) in PROBES.items():
        row = rows[ref]
        if row['net'] != net or row['source_net'] != net:
            raise ValueError(f'{ref}: wrong calibration net')
        if not row['back'] or not row['bare_copper'] or row['pads'] != 1:
            raise ValueError(f'{ref}: expected bare underside probe pad')
        if any(abs(s - 1.5) > 1e-6 for s in row['size_mm']):
            raise ValueError(f'{ref}: probe landing size changed')
        if math.dist(row['xy'], row['source_xy']) > 3:
            raise ValueError(f'{ref}: probe stub moved away from source')
        if not row['through_via']:
            raise ValueError(f'{ref}: local through-via connection missing')
    return dict(probe_pads=4, additional_gpio=0, active_injection=False)


def verify_board(board):
    import pcbnew as p
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    rows = {}
    xy = lambda q: (p.ToMM(q.x), p.ToMM(q.y))
    for ref, (_, source, pin) in PROBES.items():
        if ref not in fps: raise ValueError(f'{ref}: calibration pad missing')
        fp = fps[ref]; pads = list(fp.Pads())
        if len(pads) != 1: raise ValueError(f'{ref}: expected one probe pad')
        pad = pads[0]; src = next(q for q in fps[source].Pads() if q.GetNumber() == pin)
        rows[ref] = dict(net=pad.GetNetname(), source_net=src.GetNetname(), pads=len(pads),
                         back=fp.IsFlipped(), bare_copper=fp.IsDNP(), size_mm=xy(pad.GetSize()),
                         xy=xy(pad.GetPosition()), source_xy=xy(src.GetPosition()),
                         through_via=any(isinstance(t, p.PCB_VIA) and t.GetViaType() == p.VIATYPE_THROUGH
                             and t.GetNetname() == pad.GetNetname() and
                             math.dist(xy(t.GetPosition()), xy(pad.GetPosition())) < .1 for t in board.GetTracks()))
    return verify(rows)
