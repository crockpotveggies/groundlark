"""Replay the complete Skylark routing snapshot in an isolated temporary tree."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pcbnew as p
from project_paths import ROOT, board_dir
from replay_trenz import copper

class ReplayTests(unittest.TestCase):
    def test_complete_native_copper_and_standard_rules(self):
        name='skylark-usb';source=board_dir(name)
        original=copper(p.LoadBoard(str(source/(name+'.kicad_pcb'))))
        with tempfile.TemporaryDirectory(prefix='skylark-replay-') as tmp:
            root=Path(tmp)
            for folder in ('hw/tools','hw/shared/libraries','hw/shared/elec/skylark','hw/skylark-usb/layout'):
                shutil.copytree(ROOT/folder,root/folder)
            folder=board_dir(name,root);folder.mkdir(parents=True)
            shutil.copy2(source/(name+'.ses'),folder/(name+'.ses'))
            for args in [('skylark_layout.py',),('import_routes.py',name)]:
                subprocess.run([sys.executable,str(root/'hw/tools'/args[0]),*args[1:]],check=True)
            replay=p.LoadBoard(str(folder/(name+'.kicad_pcb')))
            self.assertEqual(original,copper(replay))
            subprocess.run(['kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(folder/(name+'.kicad_pcb'))],check=True,capture_output=True)
            report=json.loads((folder/'drc.json').read_text())
            self.assertFalse(report['violations'],report['violations'])
            self.assertFalse(report['unconnected_items'],report['unconnected_items'])

if __name__=='__main__':unittest.main()
