"""Export actual KiCad CAD to reviewable SVG/PNG previews; not manufacturing data."""
from pathlib import Path
from project_paths import board_dir
import argparse, subprocess
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('boards',nargs='*',choices=['groundlark-hat','groundlark-field-head'])
args=parser.parse_args()
for name in args.boards or ['groundlark-hat','groundlark-field-head']:
    folder=board_dir(name); preview=folder/'preview';preview.mkdir(exist_ok=True)
    # Clear only this tool's generated previews before exporting current sheets.
    for suffix in ('*.svg','*.png'):
        for old in preview.glob(suffix):old.unlink()
    subprocess.run(['kicad-cli','sch','export','svg','-o',str(preview)+'/',str(folder/(name+'.kicad_sch'))],check=True)
    for label,layers in [('layout','F.Cu,B.Cu,F.SilkS,Edge.Cuts,Dwgs.User'),('assembly','F.Cu,F.Fab,F.SilkS,Edge.Cuts,Dwgs.User')]:
        svg=preview/(label+'.svg')
        subprocess.run(['kicad-cli','pcb','export','svg','--layers',layers,'--page-size-mode','2','--exclude-drawing-sheet','--black-and-white','-o',str(svg),str(folder/(name+'.kicad_pcb'))],check=True)
    for svg in preview.glob('*.svg'):
        subprocess.run(['rsvg-convert','-w','1800','-b','white','-o',str(svg.with_suffix('.png')),str(svg)],check=True)
