"""A failed KiCad save must retain prior CAD and project rules."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
try:
 import pcbnew
 import kicad_support
except ImportError:
 pcbnew=None

@unittest.skipUnless(pcbnew,'KiCad Python is available in the hardware lab')
class SaveBoardTests(unittest.TestCase):
 def test_success_preserves_project_rules(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'board.kicad_pcb';project=path.with_suffix('.kicad_pro')
   project.write_bytes(b'{"reviewed_rules":true}\n')
   kicad_support.save_board(path,pcbnew.BOARD())
   self.assertTrue(path.read_text().startswith('(kicad_pcb'))
   self.assertEqual(project.read_bytes(),b'{"reviewed_rules":true}\n')
   self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),['board.kicad_pcb','board.kicad_pro'])
 def test_failed_save_keeps_existing_cad(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'board.kicad_pcb';path.write_text('previous CAD')
   with patch.object(kicad_support.pcb,'SaveBoard',return_value=False),self.assertRaises(OSError):
    kicad_support.save_board(path,pcbnew.BOARD())
   self.assertEqual(path.read_text(),'previous CAD')
   self.assertEqual(len(list(Path(tmp).iterdir())),1)

if __name__=='__main__':unittest.main()
