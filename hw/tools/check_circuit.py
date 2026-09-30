"""Independent circuit invariants against the actual atopile-compiled PCB."""
from pathlib import Path
from project_paths import compiled_dir, load_layout
from burrowlark_checks import magnetometer_only
import argparse,csv,json,re
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
def require(pins,ref,expected):
    for pin,net in expected.items():
        assert pins.get((ref,str(pin)))==net,(ref,pin,pins.get((ref,str(pin))),net)
def validate_hat(pins):
    require(pins,'U40',{1:'GND',2:'SENS_3V3',3:'PI_5V'})
    require(pins,'U43',{1:'PI_3V3',2:'PI_I2C_SDA',3:'PI_I2C_SCL',4:'GND',5:'GND',6:'I2C_SCL',7:'I2C_SDA',8:'SENS_3V3'})
    require(pins,'U51',{1:'CF_UART_TX',2:'GND',3:'PI_3V3',4:'PI_UART_RX',5:'PI_UART_TX',6:'CF_IO_ENABLE',7:'CF_3V3',8:'CF_UART_DRIVE'})
    require(pins,'U52',{1:'GND',2:'CF_RESET_N',3:'CF_3V3'})
    require(pins,'Q1',{1:'CF_RESET_GATE',2:'GND',3:'CF_RESET_N'})
    require(pins,'U50',{1:'CF_REG_3V3',2:'PI_5V',3:'PI_5V',4:'GND',5:'CF_SW',6:'CF_BST'})
    require(pins,'L1',{1:'CF_SW',2:'CF_REG_3V3'})
    require(pins,'R60',{1:'CF_REG_3V3',2:'CF_3V3'})
    require(pins,'C62',{1:'CF_BST',2:'CF_SW'})

    require(pins,'J1',{1:'PI_3V3',2:'PI_5V',3:'PI_I2C_SDA',5:'PI_I2C_SCL',8:'PI_UART_TX',10:'PI_UART_RX',11:'CF_RESET_GPIO',22:'CF_IO_ENABLE',37:'SENSOR_OE_N'})
    for ref in ['C1','C2','C44','C46','C48','C75']:require(pins,ref,{1:'PI_3V3',2:'GND'})
    for ref in ['C3','C40','C41','C60','C61']:require(pins,ref,{1:'PI_5V',2:'GND'})
    for ref in ['C12','C13','C14','C15','C16','C17','C18','C19','C20','C22','C24','C25','C26','C42','C43','C45','C47','C49']:require(pins,ref,{1:'SENS_3V3',2:'GND'})
    require(pins,'C21',{1:'TILT_AEXT',2:'GND'});require(pins,'C23',{1:'TILT_DEXT',2:'GND'})
    for n in range(63,66):require(pins,f'C{n}',{1:'CF_REG_3V3',2:'GND'})
    for n in list(range(66,75))+[76,77,78,79]:require(pins,f'C{n}',{1:'CF_3V3',2:'GND'})
    require(pins,'Y1',{1:'CF_3V3',2:'GND',3:'CF_MESH_CLK_RAW',4:'CF_3V3'})
    require(pins,'Y2',{1:'CF_3V3',2:'GND',3:'CF_TILE_CLK_RAW',4:'CF_3V3'})
    require(pins,'R67',{1:'CF_MESH_CLK_RAW',2:'CF_MESH_CLK'});require(pins,'R68',{1:'CF_TILE_CLK_RAW',2:'CF_TILE_CLK'})
    for row in csv.DictReader(open(ROOT/'docs/coldfoot-run1-map.csv')):
        if row['connector_pin']=='71' or not row['hat_net']:continue
        require(pins,'J5',{row['connector_pin']:row['hat_net']})
    for ref in ['U41','U42']:require(pins,ref,{1:'PI_3V3',11:'GND',12:'GND',13:'GND',22:'SENSOR_OE_N',23:'SENS_3V3',24:'SENS_3V3'})
    require(pins,'U41',{2:'PI_3V3'});require(pins,'U42',{2:'GND'})

def main(boards=('groundlark-hat','groundlark-field-head')):
    metadata=load_layout(*boards);source=(ROOT/'hw/shared/elec/parts.ato').read_text()
    blocks={m[1]:m[2] for m in re.finditer(r'^component (\w+):\n(.*?)(?=^component |\Z)',source,re.M|re.S)}
    reports=[]
    for name,meta in metadata.items():
        target='hat' if name.endswith('-hat') else 'field_head';b=p.LoadBoard(str(compiled_dir(target)/(target+'.kicad_pcb')))
        pins={(f.GetReference(),pad.GetNumber()):pad.GetNetname() for f in b.GetFootprints() for pad in f.Pads() if pad.GetNumber()}
        for part in meta['parts']:
            if not part['type']:continue
            block=blocks[part['type']]
            assert f'partnumber="{part["mpn"]}"' in block,(part['ref'],'BOM/source MPN mismatch')
            assert f'footprint="{part["local_fp"]}.kicad_mod"' in block,(part['ref'],'BOM/source footprint mismatch')
        if target=='hat':
            validate_hat(pins)
            # Mutation checks prove these invariants detect actual omissions and
            # dangerous domain cross-connections; source/PCB files are untouched.
            for mutation in ['missing_bypass','wrong_supply']:
                bad=pins.copy()
                if mutation=='missing_bypass':del bad[('C77','1')]
                else:bad[('U51','7')]='PI_5V'
                try:validate_hat(bad)
                except AssertionError:pass
                else:raise AssertionError('Mutation escaped: '+mutation)
        else:
            require(pins,'U2',{1:'SCL',2:'GND',3:'SDA',4:'GND',5:'MAG_DRDY',7:'GND',10:'V3_SENSOR',12:'V3_SENSOR',13:'V3_SENSOR',14:'GND'})
            magnetometer_only(f.GetReference() for f in b.GetFootprints())
            magnetometer_only(part['ref'] for part in meta['parts'])
            require(pins,'U1',{1:'V3',5:'V3',16:'GND',17:'V3',32:'GND',4:'NRST',6:'SENSOR_EN',14:'MAG_DRDY',21:'USB_DM',22:'USB_DP',23:'SWDIO',24:'SWCLK',29:'SCL',30:'SDA',31:'BOOT0'})
            require(pins,'J1',{'A5':'USB_CC1','B5':'USB_CC2','A6':'USB_DP','B6':'USB_DP','A7':'USB_DM','B7':'USB_DM','A4':'USB_VBUS','A9':'USB_VBUS','B4':'USB_VBUS','B9':'USB_VBUS','A1':'GND','A12':'GND','B1':'GND','B12':'GND','S1':'GND'})
            require(pins,'R1',{1:'USB_CC1',2:'GND'});require(pins,'R2',{1:'USB_CC2',2:'GND'})
            require(pins,'F1',{1:'USB_VBUS',2:'USB_5V'})
            require(pins,'U4',{1:'USB_5V',2:'GND',3:'USB_5V',5:'V3'})
            require(pins,'U5',{1:'V3',2:'GND',3:'SENSOR_EN',5:'V3_SENSOR',6:'V3_SENSOR'})
            require(pins,'R5',{1:'SENSOR_EN',2:'GND'})
            require(pins,'C1',{1:'USB_5V',2:'GND'})
            require(pins,'C8',{1:'NRST',2:'GND'})
            for n in [2,3,6,7,9]:require(pins,f'C{n}',{1:'V3',2:'GND'})
            require(pins,'C4',{1:'V3_SENSOR',2:'GND'})
        reports.append({'board':name,'compiled_pins':len(pins),'source_bom_agreement':'PASS','circuit_invariants':'PASS'})
    result={'boards':reports,'negative_mutations':['missing supervisor bypass rejected','5V on Coldfoot UART VCC rejected'] if 'groundlark-hat' in boards else []}
    if len(boards)==2:
        (ROOT/'hw/shared/simulation/circuit-checks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',choices=('groundlark-hat','groundlark-field-head'))
    args=parser.parse_args()
    main((args.board,) if args.board else ('groundlark-hat','groundlark-field-head'))
