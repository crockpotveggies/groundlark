"""Independent fault injections for supply and bias return routing."""
import hashlib
from pathlib import Path
import sys
import unittest
import pcbnew as p
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sensor_supply_layout import review

BOARD = Path(__file__).resolve().parents[1] / 'groundlark-fpga-hat/boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb'


class SupplyLayoutTests(unittest.TestCase):
    def setUp(self):
        self.sha = hashlib.sha256(BOARD.read_bytes()).hexdigest()
        self.board = p.LoadBoard(str(BOARD))

    def tearDown(self):
        self.assertEqual(self.sha, hashlib.sha256(BOARD.read_bytes()).hexdigest())

    def test_native_routes(self):
        result = review(self.board)
        self.assertEqual(len(result['ground_track_to_plane_via_mm']), 10)

    def test_old_long_bias_return_rejected(self):
        for t in list(self.board.GetTracks()):
            if isinstance(t,p.PCB_VIA) and tuple(round(x,2) for x in p.ToMM(t.GetPosition())) == (56.6,97):
                self.board.Delete(t)
        with self.assertRaisesRegex((AssertionError,ValueError), 'C93|No copper'):
            review(self.board)

    def test_unconnected_or_wrong_net_plane_is_not_a_ground_return(self):
        for zone in self.board.Zones():
            zone.SetNetCode(self.board.FindNet('SENS_3V3').GetNetCode())
        with self.assertRaisesRegex(ValueError, 'No copper'):
            review(self.board)

    def test_missing_output_bypass_rejected(self):
        next(f for f in self.board.GetFootprints() if f.GetReference()=='C43').SetDNP(True)
        with self.assertRaises(AssertionError):
            review(self.board)
