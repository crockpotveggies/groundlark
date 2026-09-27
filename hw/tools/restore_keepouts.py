"""Restore library footprint keepouts omitted by atopile's board conversion."""
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
def restore(b):
    for fp in b.GetFootprints():
        lib=p.FootprintLoad(str(ROOT/'hw/shared/elec'),fp.GetFPID().GetLibItemName())
        if not lib or not list(lib.Zones()) or list(fp.Zones()):continue
        lib.SetPosition(fp.GetPosition());lib.SetOrientation(fp.GetOrientation())
        for zone in lib.Zones():
            copy=p.ZONE(zone)
            fp.Add(copy)
        print('Restored',fp.GetReference(),'library keepouts')
if __name__=='__main__':
    path=ROOT/'hw/groundlark-coldfoot-hat/boards/groundlark-hat/groundlark-hat.kicad_pcb'
    b=p.LoadBoard(str(path));restore(b);p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b)
