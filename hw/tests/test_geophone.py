import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from geophone_checks import PINS, verify, verify_connector


class GeophoneCircuitTests(unittest.TestCase):
    def test_horizontal_entry_and_numbered_holes(self):
        pads={'1':(10.38,50.9,1.2),'2':(14.19,50.9,1.2),'3':(18,50.9,1.2)}
        footprint='PhoenixContact_MC_1,5_3-G-3.81_1x03_P3.81mm_Horizontal'
        self.assertEqual(verify_connector(pads,(0,False),footprint),3)
        for pose in ((180,False),(90,False),(0,True)):
            with self.assertRaisesRegex(ValueError,'outward-facing'):verify_connector(pads,pose,footprint)
        for bad in ({**pads,'1':pads['3'],'3':pads['1']},{**pads,'2':(14.29,50.9,1.2)},
                    {**pads,'1':(10.38,50.9,1.0)},{'1':pads['1'],'2':pads['2']}):
            with self.assertRaisesRegex(ValueError,'geometry'):verify_connector(bad,(0,False),footprint)
        with self.assertRaisesRegex(ValueError,'outward-facing'):verify_connector(pads,(0,False),'Vertical')

    def test_removed_inclinometer_and_support_parts_cannot_return(self):
        orientation={f'U{i}':(0,False) for i in range(11,14)}
        for ref in ('U20','C20','C21','C22','C23','R20'):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError,'removed inclinometer'):
                verify(PINS,{**orientation,ref:(0,False)})
        with self.assertRaisesRegex(ValueError,'removed inclinometer'):
            verify({**PINS,('J1','33'):'PI_TILT_CS'},orientation)

    def test_removed_fourth_imu_cannot_silently_return(self):
        orientation={f'U{i}':(0,False) for i in range(11,14)}
        for ref in ('U14','R14','C18','C19'):
            with self.assertRaisesRegex(ValueError,'removed fourth'):
                verify(PINS,{**orientation,ref:(0,False)})

    def test_rejects_missing_or_reversed_terminal(self):
        orientation={f'U{i}':(0,False) for i in range(11,14)}
        self.assertEqual(verify(PINS,orientation),len(PINS))
        for key in PINS:
            wrong=dict(PINS);wrong[key]='WRONG'
            with self.assertRaises(ValueError): verify(wrong,orientation)

    def test_rejects_any_rotated_or_flipped_imu(self):
        for i in range(11,14):
            for pose in ((90,False),(180,False),(0,True)):
                axes={f'U{j}':(0,False) for j in range(11,14)};axes[f'U{i}']=pose
                with self.assertRaises(ValueError):verify(PINS,axes)
