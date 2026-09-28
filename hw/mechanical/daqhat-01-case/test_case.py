"""Independent fault injections for the printable-case checks."""
import copy,json,unittest
from case import HERE,build,box,cylinder
from check import validate

class CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads((HERE/'parameters.json').read_text())
        cls.parts,cls.refs,cls.levels=build(cls.c)

    def test_valid_enclosure(self):
        self.assertEqual(validate(self.c,self.parts,self.refs,self.levels)['collisions'],0)

    def test_wrong_pi_hole_pattern_rejected(self):
        c=copy.deepcopy(self.c);c['pi_holes'][0][0]+=1
        with self.assertRaisesRegex(AssertionError,'mounting pattern'):
            validate(c,self.parts,self.refs,self.levels)

    def test_wrong_riser_height_rejected(self):
        levels=dict(self.levels);levels['hat_bottom']-=4
        with self.assertRaisesRegex(AssertionError,'riser height'):
            validate(self.c,self.parts,self.refs,levels)

    def test_missing_bearing_seat_rejected(self):
        parts=dict(self.parts);x,y=self.c['geophone_center']
        parts['base']=parts['base'].cut(cylinder(x,y,0,11.5,9))
        with self.assertRaisesRegex(AssertionError,'bearing seat'):
            validate(self.c,parts,self.refs,self.levels)

    def test_closed_usb_opening_rejected(self):
        parts=dict(self.parts);parts['cover']=parts['cover'].union(box(91,1,17,95,56,31))
        with self.assertRaisesRegex(AssertionError,'service access'):
            validate(self.c,parts,self.refs,self.levels)

    def test_oversize_heatsink_rejected(self):
        refs=dict(self.refs);refs['oversize_heatsink']=box(40,18,52,70,40,80)
        with self.assertRaisesRegex(AssertionError,'collision'):
            validate(self.c,self.parts,refs,self.levels)

    def test_wrong_geophone_diameter_rejected(self):
        c=copy.deepcopy(self.c);c['geophone_diameter']=28
        with self.assertRaisesRegex(AssertionError,'Racotech'):
            validate(c,self.parts,self.refs,self.levels)

    def test_zero_geophone_clearance_rejected(self):
        c=copy.deepcopy(self.c);c['geophone_diametral_clearance']=0
        with self.assertRaisesRegex(AssertionError,'tolerance'):
            validate(c,self.parts,self.refs,self.levels)

if __name__=='__main__':unittest.main()
