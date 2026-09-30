"""Rebuild authored power pours after native SES import; preserve all routes.

Tracks and through-vias, including the converter thermal array, are in the SES.
Resistance, temperature and transient behavior still require measurements.
"""
from pathlib import Path
import json
import pcbnew as p
from kicad_support import save_board
ROOT=Path(__file__).resolve().parents[2]
F=ROOT/'hw/groundlark-fpga-hat/boards/groundlark-daqhat-01'
PATH=F/'groundlark-daqhat-01.kicad_pcb'

def apply(board):
    nets=board.GetNetsByName()
    for zone in list(board.Zones()):
        if not zone.GetIsRuleArea() and (zone.GetNetname() in ('FPGA_VIN','PI_RAW_5V') or
                (zone.GetNetname()=='GND' and zone.GetLayer() in (p.F_Cu,p.B_Cu))):
            board.Delete(zone)
    shapes=[
        (p.F_Cu,'FPGA_VIN',[(41.8,8.5),(45.6,8.5),(45.6,10.8),(41.8,10.8)]),
        (p.F_Cu,'FPGA_VIN',[(41.8,45.2),(48,45.2),(48,49),(58,49),(58,53.5),(41.8,53.5)]),
        (p.B_Cu,'FPGA_VIN',[(38,7),(101.5,7),(101.5,40),(79.5,40),(79.5,53.5),(38,53.5)]),
        (p.F_Cu,'FPGA_VIN',[(88,34.6),(93,34.6),(93,34),(97,34),(97,34.6),(102.5,34.6),(102.5,38),(88,38)]),
        (p.F_Cu,'GND',[(84,25),(109.5,25),(109.5,51),(84,51)]),
    ]
    if 'PI_RAW_5V' in nets:
        shapes += [
            (p.F_Cu,'PI_RAW_5V',[(118,30.6),(122,30.6),(122,30),(126,30),(126,30.6),(130.7,30.6),(130.7,33.8),(118,33.8)]),
            (p.B_Cu,'PI_RAW_5V',[(118,30),(130,30),(130,34),(118,34)]),
            (p.F_Cu,'GND',[(110,20),(139.5,20),(139.5,53),(110,53)]),
        ]
    for layer,net,points in shapes:
        z=p.ZONE(board);z.SetLayer(layer);z.SetNet(nets[net])
        z.SetLocalClearance(p.FromMM(.2));z.SetMinThickness(p.FromMM(.2))
        z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(1 if net in ('FPGA_VIN','PI_RAW_5V') and layer==p.F_Cu else 0)
        z.Outline().NewOutline()
        for x,y in points:z.Outline().Append(int(p.FromMM(x+50)),int(p.FromMM(y+50)))
        board.Add(z)
    board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones())

if __name__=='__main__':
    b=p.LoadBoard(str(PATH));apply(b);save_board(str(PATH),b)
    (F/'power-distribution.json').write_text(json.dumps(dict(
        source='J83 12 V center-positive through F80/D80 to U80',
        output='U80 regulated FPGA_VIN; J80/J81 module VIN/3.3VIN contacts',
        output_allocation_A=3,output_hot_loop_limit_ohm=.015,
        copper='Front local output pour, broad back distribution, two inner ground planes; all through-vias in SES',
        note='Resistance budget is a qualification target, not extracted or measured; no fabrication approval'),indent=2)+'\n')
    print('Rebuilt FPGA converter and module distribution pours')
