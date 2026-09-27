"""Independent contact, analog gain, USB and mechanical fault fixtures."""
from pathlib import Path
import hashlib, sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pcbnew as p
from check_skylark import review
from skylark_fabrication import review as fabrication_review, stackup
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
        for ref in ('C50','C80','C81','C82','C83'):self.fps[ref].SetValue('10nF')
        with self.assertRaisesRegex(AssertionError,'feedback bandwidth'):review(self.board)

    def test_ground_referenced_powered_clamp_rejected(self):
        self.pad('Q7',2).SetNet(self.board.FindNet('GND'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_reversed_gate_supply_diode_rejected(self):
        self.pad('D4',1).SetNet(self.board.FindNet('GATE_SUPPLY'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_missing_parallel_feedback_cap_rejected(self):
        self.pad('C82',1).SetNet(self.board.FindNet('GND'))
        with self.assertRaises(AssertionError):review(self.board)

    def test_standard_stack_rejects_two_layer_physical_definition(self):
        text=BOARD.read_text()
        self.assertEqual(stackup(text)['stock_id'],'JLC04161H-7628')
        # Remove a physical copper-layer entry while retaining enabled layers.
        from stackup import block_span
        start,end=block_span(text,'(stackup')
        a,z=block_span(text[start:end],'(layer "In1.Cu"')
        with self.assertRaisesRegex(AssertionError,'physical stackup'):stackup(text[:start+a]+text[start+z:])

    def test_small_drill_and_via_in_pad_rejected(self):
        via=next(t for t in self.board.GetTracks() if isinstance(t,p.PCB_VIA))
        via.SetDrill(p.FromMM(.2))
        with self.assertRaisesRegex(AssertionError,'Standard via'):fabrication_review(self.board)
        via.SetDrill(p.FromMM(.3));via.SetPosition(self.pad('C6',1).GetPosition())
        with self.assertRaisesRegex(AssertionError,'via-in-SMT-pad'):fabrication_review(self.board)

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

    def test_removed_driven_guard_rejected(self):
        for zone in list(self.board.Zones()):
            if zone.GetNetname()=='GUARD':self.board.Delete(zone)
        with self.assertRaisesRegex(AssertionError,'Driven guard copper'):review(self.board)

if __name__=='__main__':unittest.main()
