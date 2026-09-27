"""Resume routing from the saved native PCB, retaining completed copper."""
from pathlib import Path
from project_paths import board_dir, load_layout
import sys,json
import pcbnew as p
from assemble_pcb import export_dsn
ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':
    name=sys.argv[1];folder=board_dir(name)
    board=p.LoadBoard(str(folder/(name+'.kicad_pcb')))
    # Pours are regenerated after routing; keep all authored rule areas.
    for zone in list(board.Zones()):
        if not zone.GetIsRuleArea():board.Delete(zone)
    spec=load_layout(name)[name]
    export_dsn(board,folder/(name+'.dsn'),spec.get('signal_via_mm',[.6,.3]),spec.get('ground_layers'))
    print('Exported existing copper for continued routing:',name)
