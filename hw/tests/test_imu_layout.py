from pathlib import Path
import hashlib
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from imu_layout import review, shortest
import pcbnew as p

BOARD = Path(__file__).resolve().parents[1] / 'groundlark-fpga-hat/boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb'


class ImuBypassTests(unittest.TestCase):
    def setUp(self):
        self.before = hashlib.sha256(BOARD.read_bytes()).hexdigest()
        self.board = p.LoadBoard(str(BOARD))
        self.fps = {f.GetReference(): f for f in self.board.GetFootprints()}

    def tearDown(self):
        self.assertEqual(hashlib.sha256(BOARD.read_bytes()).hexdigest(), self.before)

    def test_native_bypasses_and_returns(self):
        result = review(self.board)
        self.assertEqual(len(result['bypass_paths']), 6)
        self.assertLess(result['bypass_paths'][0]['supply_xy_mm'], 1.5)

    def test_disconnected_capacitor_rejected(self):
        self.fps['C12'].SetPosition(p.VECTOR2I(p.FromMM(51),p.FromMM(80)))
        with self.assertRaisesRegex(ValueError, 'No copper-only path'):
            review(self.board)

    def test_wrong_bypass_value_rejected(self):
        self.fps['C13'].SetValue('100pF')
        with self.assertRaisesRegex(AssertionError, '100 nF'):
            review(self.board)

    def test_dnp_bypass_rejected(self):
        self.fps['C12'].SetDNP(True)
        with self.assertRaisesRegex(AssertionError, 'DNP'):
            review(self.board)

    def test_nearby_via_without_plane_connection_rejected(self):
        for zone in list(self.board.Zones()):
            zone.SetNetCode(self.board.FindNet('SENS_3V3').GetNetCode())
        with self.assertRaisesRegex(ValueError, 'No copper-only path'):
            review(self.board)

    def test_nearby_via_on_wrong_net_rejected(self):
        for track in self.board.GetTracks():
            if isinstance(track,p.PCB_VIA) and track.GetNetname() == 'GND':
                track.SetNetCode(self.board.FindNet('SENS_3V3').GetNetCode())
        with self.assertRaisesRegex(ValueError, 'No copper-only path'):
            review(self.board)

    def test_graph_measures_detour_not_straight_line_distance(self):
        self.assertEqual(shortest({0:[(1,5)],1:[(2,5)],2:[]},[0],{2}),10)
        with self.assertRaises(ValueError):
            shortest({0:[],2:[]},[0],{2})

    def test_connected_long_supply_route_rejected(self):
        # Inject an over-limit route measurement while preserving connectivity. This
        # injects a geometric regression without touching the saved CAD.
        from unittest.mock import patch
        from imu_layout import Copper
        original = Copper.between
        def detour(graph, a, b):
            return original(graph,a,b) + 10
        with patch.object(Copper,'between',detour):
            with self.assertRaisesRegex(AssertionError,'supply path'):
                review(self.board)


if __name__ == '__main__':
    unittest.main()
