"""Remove exact duplicate conductors and sub-micron router roundoff segments."""
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];path=ROOT/'hw/groundlark-coldfoot-hat/boards/groundlark-hat/groundlark-hat.kicad_pcb'
b=p.LoadBoard(str(path));seen={};removed=0
for t in list(b.GetTracks()):
    if t.GetClass()=='PCB_VIA':key=('via',t.GetNetname(),tuple(t.GetPosition()),t.GetWidth(p.F_Cu),t.GetDrillValue())
    else:
        if t.GetLength()<p.FromMM(.001) and not t.IsLocked():b.Delete(t);removed+=1;continue
        key=('track',t.GetNetname(),tuple(sorted((tuple(t.GetStart()),tuple(t.GetEnd())))),t.GetLayer(),t.GetWidth())
    if key in seen:
        seen[key].SetLocked(seen[key].IsLocked() or t.IsLocked());b.Delete(t);removed+=1
    else:seen[key]=t
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b);print('Removed',removed,'duplicate/roundoff objects')
