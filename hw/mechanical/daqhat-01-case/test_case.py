"""Independent fault injections for the printable-case checks."""
import copy,json,unittest
from case import HERE,build,box,cylinder
from check import validate

class CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads((HERE/'parameters.json').read_text())
        cls.parts,cls.refs,cls.levels=build(cls.c)

    def test_blocked_sma_access_rejected(self):
        parts=dict(self.parts);parts['cover']=parts['cover'].union(box(93,-46,42,95,-44,50))
        with self.assertRaisesRegex(AssertionError,'GNSS SMA plug access'):
            validate(self.c,parts,self.refs,self.levels)

    def test_sma_on_wrong_side_rejected(self):
        refs=dict(self.refs);refs['gnss_sma']=refs['gnss_sma'].mirror('YZ')
        with self.assertRaisesRegex(AssertionError,'SMA handedness'):
            validate(self.c,self.parts,refs,self.levels)

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
        parts=dict(self.parts);x,y=self.c['geophone_center'];y=-y
        parts['base']=parts['base'].cut(cylinder(x,y,0,11.5,9))
        with self.assertRaisesRegex(AssertionError,'bearing seat'):
            validate(self.c,parts,self.refs,self.levels)

    def test_obstructed_usb_opening_rejected(self):
        parts=dict(self.parts)
        # A tab hangs into the plug envelope from the wall above the opening.
        wall=box(-63,-30,25,-62,-22,31) if self.c['stack_rotation_deg']==180 else box(91,-56,17,95,-1,31)
        parts['cover']=parts['cover'].union(wall)
        with self.assertRaisesRegex(AssertionError,'service access'):
            validate(self.c,parts,self.refs,self.levels)

    def test_support_blocking_usb_plug_rejected(self):
        parts=dict(self.parts);parts['base']=parts['base'].union(box(-25,-4,5,-22,-1,39))
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

    def test_blocked_rotated_mount_rejected(self):
        parts=dict(self.parts)
        parts['base']=parts['base'].union(cylinder(81.5,-52.5,0,1.4,10))
        with self.assertRaisesRegex(AssertionError,'mounting bore'):
            validate(self.c,parts,self.refs,self.levels)

    def test_connector_on_wrong_side_rejected(self):
        refs=dict(self.refs)
        refs['geophone_plug']=box(8,43,41,21,59,61)
        with self.assertRaisesRegex(AssertionError,'connector must face'):
            validate(self.c,self.parts,refs,self.levels)

    def test_blocked_horizontal_connector_withdrawal_rejected(self):
        parts=dict(self.parts)
        parts['base']=parts['base'].union(box(70,28,0,72,30,49))
        with self.assertRaisesRegex(AssertionError,'withdrawal blocked'):
            validate(self.c,parts,self.refs,self.levels)

    def test_mirrored_pi_power_port_rejected(self):
        refs=dict(self.refs);refs['pi_power']=refs['pi_power'].mirror('XZ')
        with self.assertRaisesRegex(AssertionError,'physical handedness'):
            validate(self.c,self.parts,refs,self.levels)

    def test_mirrored_gpio_side_rejected(self):
        refs=dict(self.refs);refs['gpio_stack']=refs['gpio_stack'].mirror('XZ')
        with self.assertRaisesRegex(AssertionError,'physical handedness'):
            validate(self.c,self.parts,refs,self.levels)

    def test_obstructed_power_route_rejected(self):
        parts=dict(self.parts);parts['base']=parts['base'].union(box(70,20,5,76,23,19))
        with self.assertRaisesRegex(AssertionError,'USB-C insertion blocked'):
            validate(self.c,parts,self.refs,self.levels)

    def test_old_hat_outline_rejected(self):
        refs=dict(self.refs);refs['hat']=box(0,-56,self.levels['hat_bottom'],85,0,self.levels['hat_top'])
        with self.assertRaisesRegex(AssertionError,'extension missing'):
            validate(self.c,self.parts,refs,self.levels)

    def test_wrong_fpga_jack_side_rejected(self):
        refs=dict(self.refs);refs['j83']=refs['j83'].mirror('XZ')
        with self.assertRaisesRegex(AssertionError,'jack handedness'):
            validate(self.c,self.parts,refs,self.levels)

    def test_missing_power_wing_support_rejected(self):
        parts=dict(self.parts);parts['base']=parts['base'].cut(box(-25,-55,6,-22,-52,41))
        with self.assertRaisesRegex(AssertionError,'wing support missing'):
            validate(self.c,parts,self.refs,self.levels)

    def test_missing_power_wing_end_stop_rejected(self):
        parts=dict(self.parts);parts['base']=parts['base'].cut(box(-22,.3,6,-19,3.3,42))
        with self.assertRaisesRegex(AssertionError,'end stop missing'):
            validate(self.c,parts,self.refs,self.levels)

    def test_blocked_barrel_plug_rejected(self):
        parts=dict(self.parts);parts['cover']=parts['cover'].union(box(-18,-65,45,-16,-63,50))
        with self.assertRaisesRegex(AssertionError,'plug access blocked'):
            validate(self.c,parts,self.refs,self.levels)

    def test_blocked_switch_access_rejected(self):
        parts=dict(self.parts);parts['cover']=parts['cover'].union(box(-25,-51,72,-15,-41,75))
        with self.assertRaisesRegex(AssertionError,'switch access blocked'):
            validate(self.c,parts,self.refs,self.levels)

    def test_blocked_battery_plug_rejected(self):
        parts=dict(self.parts);parts['cover']=parts['cover'].union(box(-40,-65,45,-38,-63,50))
        with self.assertRaisesRegex(AssertionError,'Battery plug access blocked'):
            validate(self.c,parts,self.refs,self.levels)

    def test_missing_supervisor_support_rejected(self):
        parts=dict(self.parts);parts['base']=parts['base'].cut(box(-55,-55,6,-52,-52,41))
        with self.assertRaisesRegex(AssertionError,'Supervisor wing support missing'):
            validate(self.c,parts,self.refs,self.levels)

if __name__=='__main__':unittest.main()
