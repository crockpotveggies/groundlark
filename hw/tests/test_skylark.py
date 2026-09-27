"""Independent contact, analog gain, USB and mechanical fault fixtures."""
from pathlib import Path
import hashlib, sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pcbnew as p
from check_skylark import review
from project_paths import board_dir

BOARD=board_dir('skylark-usb')/'skylark-usb.kicad_pcb'

class SkylarkTests(unittest.TestCase):
    def setUp(self):
        self.digest=hashlib.sha256(BOARD.read_bytes()).hexdigest()
        self.board=p.LoadBoard(str(BOARD));self.fps={f.GetReference():f for f in self.board.GetFootprints()}

    def tearDown(self):
        self.assertEqual(hashlib.sha256(BOARD.read_bytes()).hexdigest(),self.digest)

    def pad(self,ref,num):
        return next(x for x in self.fps[ref].Pads() if x.GetNumber()==str(num))

    def test_native_design(self):
        self.assertGreater(review(self.board)['contacts'],350)

    def test_reference_counter_swap_rejected(self):
        self.pad('GS1','RE').SetNet(self.board.FindNet('SO2_CE'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_bottom_view_not_mirrored_rejected(self):
        a=self.pad('GS2','RE');b=self.pad('GS2','CE');q=a.GetPosition()
        a.SetPosition(b.GetPosition());b.SetPosition(q)
        with self.assertRaisesRegex(AssertionError,'Gas socket pin geometry'):review(self.board)

    def test_wrong_h2s_gain_rejected(self):
        self.fps['R51'].SetValue('100000R')
        with self.assertRaisesRegex(AssertionError,'TIA gain'):review(self.board)

    def test_five_volts_on_humidity_sensor_rejected(self):
        self.pad('U11',3).SetNet(self.board.FindNet('USB_5V'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_missing_cc_resistor_rejected(self):
        self.fps['R2'].SetDNP(True)
        with self.assertRaises(AssertionError):review(self.board)

    def test_pms_tx_rx_swap_rejected(self):
        self.pad('J2',4).SetNet(self.board.FindNet('PM_TX'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_connected_reserved_contact_rejected(self):
        self.pad('J2',7).SetNet(self.board.FindNet('GND'))
        with self.assertRaisesRegex(AssertionError,'Deliberate NC connected'):review(self.board)

    def test_via_on_usb_pair_rejected(self):
        via=p.PCB_VIA(self.board);via.SetNet(self.board.FindNet('USB_DP'));self.board.Add(via)
        with self.assertRaisesRegex(AssertionError,'USB route layer/via'):review(self.board)

    def test_analog_switch_bypassed_rejected(self):
        self.pad('R19',1).SetNet(self.board.FindNet('V3'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_clamps_not_engaged_at_reset_rejected(self):
        self.pad('R73',1).SetNet(self.board.FindNet('GND'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_high_bandwidth_feedback_rejected(self):
        self.fps['C50'].SetValue('10nF')
        with self.assertRaisesRegex(AssertionError,'feedback bandwidth'):review(self.board)

    def test_excessive_adc_source_impedance_rejected(self):
        self.fps['R32'].SetValue('100000R')
        self.fps['C31'].SetValue('100nF')
        with self.assertRaisesRegex(AssertionError,'source resistance'):review(self.board)

    def test_via_on_sensitive_input_rejected(self):
        via=p.PCB_VIA(self.board);via.SetNet(self.board.FindNet('SO2_WE_SUM'));self.board.Add(via)
        with self.assertRaisesRegex(AssertionError,'summing route layer/via'):review(self.board)

    def test_old_amplifier_package_rejected(self):
        self.fps['U7'].SetFPID(p.LIB_ID('Skylark','SOIC-8_3.9x4.9mm_P1.27mm'))
        with self.assertRaisesRegex(AssertionError,'Amplifier package'):review(self.board)

    def test_missing_local_supply_connection_rejected(self):
        target=self.pad('C37',1)
        for track in list(self.board.GetTracks()):
            if track.GetNetname()=='VA' and (target.HitTest(track.GetStart()) or target.HitTest(track.GetEnd())):
                self.board.Delete(track)
        with self.assertRaises((AssertionError,ValueError)):review(self.board)

    def test_missing_backside_bypass_return_rejected(self):
        target=self.pad('C37',2)
        for track in list(self.board.GetTracks()):
            if track.GetNetname()=='GND' and track.GetLayer()==p.B_Cu and (target.HitTest(track.GetStart()) or target.HitTest(track.GetEnd())):
                self.board.Delete(track)
        with self.assertRaises((AssertionError,ValueError)):review(self.board)

if __name__=='__main__':unittest.main()
