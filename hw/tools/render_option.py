"""Render optional pressure-sensor population without changing the delivered PCB."""
from pathlib import Path
import pcbnew as p,subprocess
R=Path(__file__).resolve().parents[2];folder=R/'hw/burrowlark-usb/boards/groundlark-field-head'
b=p.LoadBoard(str(folder/'groundlark-field-head.kicad_pcb'))
next(f for f in b.GetFootprints() if f.GetReference()=='U3').SetDNP(False)
temp=folder/'.render-infrasound-option.kicad_pcb'
try:
 p.SaveBoard(str(temp),b)
 subprocess.run(['xvfb-run','-a','kicad-cli','pcb','render','--width','1800','--height','1000','--quality','high','--background','opaque','--rotate','325,0,25','--zoom','0.85','-o',str(folder/'3d-infrasound-option.png'),str(temp)],check=True)
finally:temp.unlink(missing_ok=True)
