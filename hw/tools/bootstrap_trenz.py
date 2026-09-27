"""One-time A2-derived Trenz variant authoring. Maintained circuit is hat_trenz.ato.

Legacy pre-expansion authoring only: this does not include J86-J89.
Run only when intentionally resetting this variant's circuit and placement.
Vendor module pin numbers are mapped to opposite-parity carrier pad numbers.
"""
from pathlib import Path
from project_paths import load_layout
import re,json,copy,types
import pcbnew as p
from kicad_support import libsym
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'hw/shared/elec'
old=(ROOT/'hw/groundlark-coldfoot-hat/elec/hat.ato').read_text()
body=old.split('    sensor_supply =')[1].split('    # Run-1 1x1 Coldfoot carrier')[0]
body='    sensor_supply ='+body
body+=old[old.index('    u51 = new'):old.index('    # 25MHz /')]
body=body.replace('CF_','FPGA_')
body=body.replace('05-coldfoot-interface','05-fpga-interface').replace('Coldfoot UART','FPGA UART')
# Atomic definitions stay shared with A2.
body=re.sub(r'new FPGA_', 'new CF_',body)
parts=load_layout('groundlark-hat', 'groundlark-field-head')['groundlark-hat']['parts']
keep={'U51','C75','C76','R61','R62','R63','U52','C77','R64','Q1','R65','R66'}
parts=[copy.deepcopy(x) for x in parts if not (x['type'] or '').startswith('CF_') or x['ref'] in keep]
for x in parts:
    x['value']=x['value'].replace('Coldfoot','FPGA');x['note']=x['note'].replace('Coldfoot','FPGA')
    if x['ref']=='J4':x['xy']=[135,42]
positions={'TP1':[74,37],'TP2':[74,40],'U51':[73,12],'C75':[70,9],'C76':[76,9],'R61':[74,16],
 'R62':[69,16],'R63':[77,18],'U52':[92,30],'C77':[92,34],
 'R64':[96,30],'Q1':[97,23],'R65':[94,19],'R66':[99,19]}
for x in parts:
    if x['ref'] in positions:x['xy']=positions[x['ref']]
    if x['ref'] in keep:x['section']='07-fpga-host-isolation'
newtypes={};connections={}
def part(ref,typ,mpn,lib,fpname,xy,pins,section='08-trenz-carrier',angle=0,note='',names=None,voltage=None):
    global body
    local='TZ_'+typ
    fp=p.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty',fpname)
    assert fp,(lib,fpname)
    # Numeric shield terminal is shared by both shield solder tabs.
    maxpin=max([int(q.GetNumber()) for q in fp.Pads() if q.GetNumber().isdigit()] or [0])
    for pad in fp.Pads():
        if pad.GetNumber()=='SH':pad.SetNumber(str(maxpin+1))
    fp.SetFPID(p.LIB_ID('Groundlark',local))
    p.FootprintSave(str(E),fp)
    nums=sorted({q.GetNumber() for q in fp.Pads() if q.GetNumber()},key=int)
    meta=dict(ref=ref,value=mpn,mpn=mpn,footprint=lib+':'+fpname,local_fp=local,xy=xy,
              angle=angle,type=typ,section=section,note=note,names=names or {},dnp=False)
    parts.append(meta)
    if typ not in newtypes:
        symbol=types.SimpleNamespace(**{**meta,'ref':typ,'pins':dict.fromkeys(nums)})
        s=libsym(symbol)[0].replace('Groundlark:Part_'+typ,typ).replace('Part_'+typ,typ)
        (E/'symbols'/f'{typ}.kicad_sym').write_text('(kicad_symbol_lib (version 20231120) (generator kicad_symbol_editor) '+s+')')
        desc=f'component {typ}:\n    trait is_atomic_part<manufacturer="See BOM source", partnumber="{mpn}", footprint="{local}.kicad_mod", symbol="symbols/{typ}.kicad_sym">\n    trait has_designator_prefix<prefix="{ref[0]}">\n'
        desc+=''.join(f'    signal p{n} ~ pin {n}\n' for n in nums)
        newtypes[typ]=desc
    body+=f'\n    # {ref}: {mpn}; {note}\n    {ref.lower()} = new {typ}\n    trait {ref.lower()} has_designator<designator="{ref}">\n'
    for num,net in pins.items():body+=f'    {ref.lower()}.p{num} ~ {net}\n'
    connections[ref]={str(k):v for k,v in pins.items()}

jm1={1:'FPGA_VIN',3:'FPGA_VIN',5:'FPGA_VIN',9:'FPGA_3V3',11:'FPGA_3V3',13:'FPGA_VIN',15:'FPGA_VIN',14:'FPGA_3V3',7:'FPGA_NOSEQ',28:'FPGA_EN1',30:'FPGA_PGOOD',32:'FPGA_MODE',89:'FPGA_JTAGEN'}
jm2={2:'FPGA_VIN',4:'FPGA_VIN',6:'FPGA_VIN',8:'FPGA_VIN',1:'FPGA_3V3',3:'FPGA_3V3',7:'FPGA_3V3',9:'FPGA_3V3',10:'FPGA_3V3',12:'FPGA_3V3',91:'FPGA_3V3',93:'JTAG_TMS',95:'JTAG_TDI',97:'JTAG_TDO',99:'JTAG_TCK',18:'FPGA_CONFIG_RESET_N',11:'FPGA_UART_RX',13:'FPGA_UART_TX',14:'FPGA_RESET_N',16:'FPGA_AUX0',15:'FPGA_AUX1',17:'FPGA_AUX2'}
jm3={}
for i in [2,8,20,26,29,34,44,53,54,63,64,73,74,84,90]:jm1[i]='GND'
for i in [20,39,40,49,50,59,60,69,70,79,80,90]:jm2[i]='GND'
for i in [5,6,11,12,17,18,23,24,29,30,35,36,45,46]:jm3[i]='GND'
audit=[]
for ref,jm,xy,n,angle in [('J80',jm1,[105,44],50,0),('J81',jm2,[105,12],50,0),('J82',jm3,[84,28],30,90)]:
    pins={i+1 if i%2 else i-1:net for i,net in jm.items()};pins[n*2+1]='GND'
    mod={'J80':'JM1','J81':'JM2','J82':'JM3'}[ref]
    for i,net in jm.items():audit.append(dict(module_connector=mod,module_pin=i,carrier_ref=ref,carrier_pad=i+1 if i%2 else i-1,net=net))
    part(ref,'TZ100' if n==50 else 'TZ60',f'LSHM-1{n:02d}-04.0-L-DV-A-S-K-TR','Connector_Samtec',f'Samtec_LSHM-1{n:02d}-xx.x-x-DV-S_2x{n:02d}-1SH_P0.50mm_Vertical',xy,pins,section='08-trenz-'+mod,angle=angle,note=f'Mates {mod}; opposite parity; 8 mm board surface gap')

part('J83','TZ_POWER','1715721','TerminalBlock_Phoenix','TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',[137.5,9],{1:'EXT_3V3',2:'GND'},angle=90,note='REGULATED 3.3 V ONLY; current-limited external supply, 3 A initial operating budget')
part('F80','TZ_FUSE','0467005.NR','Fuse','Fuse_1206_3216Metric',[127,4],{1:'EXT_3V3',2:'FPGA_VIN'},note='5 A fast fuse; not reverse-polarity or overvoltage protection')
part('J84','TZ_JTAG','TSW-106-07-G-S','Connector_PinHeader_2.54mm','PinHeader_1x06_P2.54mm_Vertical',[135,22],{1:'JTAG_TMS',2:'JTAG_TDI',3:'JTAG_TDO',4:'JTAG_TCK',5:'GND',6:'FPGA_3V3'},note='Digilent 6-pin JTAG signal order; reference is an output, not a power input')
part('J85','TZ_AUX','TSW-103-07-G-D','Connector_PinHeader_2.54mm','PinHeader_2x03_P2.54mm_Vertical',[111,26],{1:'FPGA_AUX0',2:'GND',3:'FPGA_AUX1',4:'GND',5:'FPGA_AUX2',6:'GND'},note='3.3 V spare I/O; fit cable before stacking')
part('JP80','TZ_JP','TSW-102-07-G-S','Connector_PinHeader_2.54mm','PinHeader_1x02_P2.54mm_Vertical',[87,50],{1:'FPGA_EN1',2:'GND'},note='Fit shunt to DISABLE module; open enables on-board sequence')
part('JP81','TZ_JP','TSW-102-07-G-S','Connector_PinHeader_2.54mm','PinHeader_1x02_P2.54mm_Vertical',[94,50],{1:'FPGA_CONFIG_RESET_N',2:'GND'},note='Fit shunt to request module configuration reset')
for ref,net,xy in [('R80','FPGA_JTAGEN',[123,36]),('R81','FPGA_NOSEQ',[89,40])]:
    body+=f'\n    {ref.lower()} = new P_10\n    trait {ref.lower()} has_designator<designator="{ref}">\n    {ref.lower()}.p1 ~ {net}\n    {ref.lower()}.p2 ~ GND\n'
    template=copy.deepcopy(next(x for x in parts if x['ref']=='R11'));template.update(ref=ref,xy=xy,section='08-trenz-carrier',note='FPGA JTAG selection / spare CPLD control idle pull-down');parts.append(template)
for ref,net,xy,typ in [('C80','FPGA_VIN',[105,51],'P_22'),('C81','FPGA_VIN',[90,5],'P_22'),('C82','FPGA_VIN',[119,5],'P_22'),('C83','FPGA_VIN',[115,5],'P_6'),('C84','FPGA_3V3',[91,17],'P_13'),('C85','FPGA_3V3',[101,38],'P_13')]:
    body+=f'\n    {ref.lower()} = new {typ}\n    trait {ref.lower()} has_designator<designator="{ref}">\n    {ref.lower()}.p1 ~ {net}\n    {ref.lower()}.p2 ~ GND\n'
    template=copy.deepcopy(next(x for x in parts if x['type']==typ));template.update(ref=ref,xy=xy,section='09-fpga-power',note='Carrier local decoupling; module contains core decoupling');parts.append(template)
# Module mounting: four 3.2 mm clearance holes on 44 x 34 mm rectangle.
for ref,xy in zip(['H80','H81','H82','H83'],[[83,11],[127,11],[83,45],[127,45]]):
    part(ref,'TZ_HOLE','M3 / 8 mm spacer','MountingHole','MountingHole_3.2mm_M3',xy,{},section='10-mechanical')
    parts[-1]['type']=''
    # Mechanical-only footprints are not electrical components.
    body=re.sub(r'\n    # '+ref+r':.*?(?=\n    # |\Z)','',body,flags=re.S)
newtypes.pop('TZ_HOLE',None)
body+='\n    fpga_supply = new ElectricPower\n    fpga_supply.hv ~ FPGA_3V3\n    fpga_supply.lv ~ GND\n    fpga_supply.voltage = 3.201V to 3.399V\n    assert fpga_supply.voltage within 3.0V to 3.6V\n'
body+='    external_supply = new ElectricPower\n    external_supply.hv ~ FPGA_VIN\n    external_supply.lv ~ GND\n    external_supply.voltage = 3.201V to 3.399V\n    assert external_supply.voltage within 3.201V to 3.399V\n'
signals=sorted(set(re.findall(r'~ ([A-Z][A-Z_0-9]*)',body)))
imports=sorted(set(re.findall(r'= new (\w+)',body))-{'ElectricPower'})
header='# Trenz TE0712-03-81I36-A variant. Electrical source of truth.\n#pragma experiment("TRAITS")\nimport has_designator\nimport ElectricPower\nimport has_net_name_suggestion\n'
header+=''.join(f'from "{"trenz_parts.ato" if x in newtypes else "../../shared/elec/parts.ato"}" import {x}\n' for x in imports)
header+='\nmodule TrenzHat:\n'+''.join(f'    signal {x}\n' for x in signals)+'\n'
body+=''.join(f'    trait {x} has_net_name_suggestion<name="{x}", level="EXPECTED">\n' for x in signals)
(ROOT/'hw/groundlark-fpga-hat/elec/hat_trenz.ato').write_text(header+body)
(ROOT/'hw/groundlark-fpga-hat/elec/trenz_parts.ato').write_text('# Manufacturer-selected carrier components.\n#pragma experiment("TRAITS")\nimport is_atomic_part\nimport has_designator_prefix\n\n'+'\n'.join(newtypes.values()).replace('footprint="', 'footprint="../../shared/elec/').replace('symbol="', 'symbol="../../shared/elec/'))
# Pi-outline revision: module is centered over the right-hand sensor circuitry.
fixed={'J80':([55,44],0),'J81':([55,12],0),'J82':([34,28],90),
 'H80':([33,11],0),'H81':([77,11],0),'H82':([33,45],0),'H83':([77,45],0),
 'J83':([7,12],270),'J84':([82.5,19],0),'J4':([82.5,37],0),
 'J85':([43,52],90),'JP80':([68,52],90),'JP81':([75,52],90),
 'U11':([13,24],0),'U12':([24,24],0),'U13':([13,36],0),'U14':([24,36],0),
 'U20':([45,28],0),'U21':([14,46],0),'J2':([25,46],0),
 'U41':([60,23],0),'U42':([60,35],0),'U1':([73,24],0),
 'U43':([42,18],0),'U40':([73,36],0),'U51':([21,13],0),
 'U52':([45,38],0),'Q1':([50,38],0),'F80':([14,10],0)}
for meta in parts:
    if meta['ref'] in fixed:meta['xy'],meta['angle']=fixed[meta['ref']]
    if meta['ref']=='J85':meta['note']='3.3 V spare I/O at accessible lower edge'
    if meta['ref']=='J83':meta['note']='REGULATED 3.3 V ONLY; external current-limited supply; 3 A initial operating budget'
(ROOT/'hw/groundlark-fpga-hat/layout/placement.json').write_text(json.dumps({'groundlark-daqhat-01':{'target':'trenz_hat','size':[85,56],'parts':parts}},indent=2))
(ROOT/'docs/trenz-pin-map.json').write_text(json.dumps(audit,indent=2))
print('Authored',len(parts),'parts;',len(audit),'mapped module connections')
