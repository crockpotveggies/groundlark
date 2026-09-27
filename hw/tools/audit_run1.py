from pathlib import Path
import sexpdata as sx,json,csv
from inspect_references import children,child
ROOT=Path(__file__).resolve().parents[2]
b=sx.load(open(ROOT/'hw/shared/vendor/wafer-space/1x1-mezzanine.kicad_pcb'))
rows=[]
for fp in children(b,'footprint'):
    props={x[1]:x[2] for x in children(fp,'property')}
    print(props.get('Reference'),props.get('Value'),fp[1],child(fp,'at'),'pads',len(children(fp,'pad')))
    for pad in children(fp,'pad'):
        values={str(x[0]):x[1:] for x in pad if isinstance(x,list)}
        rows.append([props.get('Reference',''),pad[1],values.get('net',[''])[-1],values.get('pinfunction',[''])[0]])
with open(ROOT/'docs/run1-module-pin-audit.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['reference','pad','actual_net','symbol_alias']);w.writerows(rows)
for row in rows:
    if row[0] in ('U101','U102','J1','U1','U2'):print(row)
print('Outline',children(b,'gr_rect'),children(b,'gr_line')[:4])
