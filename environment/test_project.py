"""Regression checks for product-local CAD dependency discovery."""
from pathlib import Path
import tempfile
import unittest
from check_project import check


class ProjectStructureTests(unittest.TestCase):
    def test_missing_model_in_product_board_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'README.md').write_text('Fixture')
            (root / 'AGENTS.md').write_text('Fixture')
            board = root / 'hw/skylark-usb/boards/example'
            board.mkdir(parents=True)
            (board / 'example.kicad_pcb').write_text(
                '(model "${KIPRJMOD}/../../../shared/models/example.step")')
            with self.assertRaisesRegex(RuntimeError, 'missing CAD dependency'):
                check(root)
            model = root / 'hw/shared/models/example.step'
            model.parent.mkdir(parents=True)
            model.write_text('fixture')
            self.assertEqual(check(root)['cad_references'], 1)
