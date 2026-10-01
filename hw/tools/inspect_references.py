"""Read vendor CAD and local KiCad symbols; no upstream code is executed."""
from pathlib import Path
import subprocess
import sexpdata as sx

ROOT = Path(__file__).resolve().parents[2]

def children(node, name):
    return [x for x in node if isinstance(x, list) and x and str(x[0]) == name]

def child(node, name):
    return next(iter(children(node, name)), None)

def inspect():
    for pdf in (ROOT/'hw/shared/reference').glob('*.pdf'):
        subprocess.run(['pdftotext', '-layout', str(pdf), str(pdf.with_suffix('.txt'))], check=True)
    for lib in ['Sensor_Motion','Sensor_Pressure','Interface','RF_GPS','Regulator_Linear','Memory_EEPROM']:
        path=Path('/usr/share/kicad/symbols')/(lib+'.kicad_sym')
        syms=sx.load(open(path))
        for sym in children(syms,'symbol'):
            if any(s in sym[1] for s in ['LSM6','SCL3300','PCA9615','MAX-M10','AP2112K-3.3','24LC32']):
                print('SYMBOL',lib,sym[1])
                for unit in children(sym,'symbol'):
                    for pin in children(unit,'pin'):
                        print(child(pin,'number')[1],child(pin,'name')[1],pin[1])

if __name__=='__main__': inspect()
