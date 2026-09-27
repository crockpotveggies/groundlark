"""Record actual wafer.space pad nets separately from legacy symbol aliases."""
from pathlib import Path
import csv,sexpdata as sx
ROOT=Path(__file__).resolve().parents[2]
def children(n,key): return [x for x in n if isinstance(x,list) and x and str(x[0])==key]
board=sx.load(open(ROOT/'hw/shared/vendor/wafer-space/0p5x0p5-cob.kicad_pcb'))
with open(ROOT/'docs/run2-module-pin-audit.csv','w',newline='') as f:
    writer=csv.writer(f);writer.writerow(['reference','pad','actual_net','symbol_alias'])
    for fp in children(board,'footprint'):
        props={x[1]:x[2] for x in children(fp,'property')};pads=children(fp,'pad')
        if len(pads)<40: continue
        for pad in pads:
            values={str(x[0]):x[1:] for x in pad if isinstance(x,list)}
            writer.writerow([props.get('Reference',''),pad[1],values.get('net',[''])[-1],values.get('pinfunction',[''])[0]])
