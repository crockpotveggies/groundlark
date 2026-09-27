"""Render actual KiCad geometry and explicitly conceptual assembly models."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'hw/groundlark-fpga-hat/boards/groundlark-daqhat-01'
(ROOT/'hw/logs').mkdir(parents=True,exist_ok=True)
for pcb,png,angle,zoom in [
 ('groundlark-daqhat-01','3d-bottom','145,0,205','.9'),
 ('groundlark-daqhat-01','3d','325,0,25','.9'),
 ('trenz-mounted','trenz-mounted','315,0,30','.8'),
 ('pi-trenz-stack-concept','pi-trenz-stack-concept','300,0,30','.78'),
 ('stack-service-envelopes','stack-service-envelopes','300,0,30','.68'),
 ('stack-exploded','stack-exploded','305,0,30','.62')]:
    if len(sys.argv)>1 and png not in sys.argv[1:]:continue
    with open(ROOT/'hw/logs'/('render-'+png+'.log'),'w') as log:
        subprocess.run(['xvfb-run','-a','kicad-cli','pcb','render','--width','1800','--height','1200','--quality','high','--background','opaque','--rotate',angle,'--zoom',zoom,'-o',str(F/(png+'.png')),str(F/(pcb+'.kicad_pcb'))],check=True,stdout=log,stderr=subprocess.STDOUT)
    print(png+'.png')
