"""Emit paginated review schematics from the compiled/routed board connectivity."""
from pathlib import Path
from project_paths import board_dir
import json,types,collections,sys
from kicad_support import save_board
import pcbnew as p
from kicad_support import schematic,uid
ROOT=Path(__file__).resolve().parents[2]
def main():
    for name in sys.argv[1:] or ['groundlark-hat','groundlark-field-head']:
        folder=board_dir(name);path=folder/(name+'.kicad_pcb');b=p.LoadBoard(str(path))
        data=json.loads((folder/'electrical.json').read_text());fps={f.GetReference():f for f in b.GetFootprints()}
        degree=collections.Counter(pad.GetNetname() for f in b.GetFootprints() for pad in f.Pads() if pad.GetNumber())
        counts=collections.Counter();parts=[]
        for meta in data['parts']:
            # Mechanical holes have no electrical pads and need no empty sheet.
            if not any(pad.GetNumber() for pad in fps[meta['ref']].Pads()):continue
            section=meta['section'].split('-page-')[0];page=counts[section]//12+1;counts[section]+=1
            meta['section']=section+f'-page-{page:02d}'
            fp=fps[meta['ref']]
            meta['pins']={pad.GetNumber():pad.GetNetname() if degree[pad.GetNetname()]>1 else None for pad in fp.Pads() if pad.GetNumber()}
            fp.SetPath(p.KIID_PATH('/'+uid(name)+'/'+uid(name+'/'+meta['section'])+'/'+uid(name+'/'+meta['ref'])))
            parts.append(types.SimpleNamespace(**meta))
        schematic(name,{'size':data['size_mm'],'parts':parts},folder)
        # Remove superseded generated sheets so only the current hierarchy is
        # offered to reviewers. Root and all referenced paginated sheets remain.
        active={name+'.kicad_sch'}|{x.section+'.kicad_sch' for x in parts}
        for old in folder.glob('*.kicad_sch'):
            if old.name not in active and old.name[:2].isdigit():old.unlink()
        save_board(str(path),b);(folder/'electrical.json').write_text(json.dumps(data,indent=2))
        print(name,'review sheets',len({x.section for x in parts}))
if __name__=='__main__':main()
