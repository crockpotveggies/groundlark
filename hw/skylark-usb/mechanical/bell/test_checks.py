"""Independent obstruction fault fixtures for the enclosure's air-path checks."""
import unittest
from enclosure import build, box, cy
from check import validate_air_paths, validate_mount_and_service, validate_sensor_packing, validate_bottom_ventilation, validate_modular_assembly

class AirPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parts,cls.refs=build()
        cls.parts={k:v for k,v in parts.items() if k!='fit-coupon'}

    def test_as_authored(self):
        validate_air_paths(self.parts)
        validate_sensor_packing(self.refs)
        validate_bottom_ventilation(self.parts,self.refs)
        validate_modular_assembly(self.parts,self.refs)

    def test_cover_screw_obstruction_is_rejected(self):
        fault=dict(self.parts)
        fault['obstruction']=box(15,-35,15,17,-33,18)
        with self.assertRaisesRegex(AssertionError,'New assembly screw obstructed'):
            validate_modular_assembly(fault,self.refs)

    def test_tie_eye_blockage_is_rejected(self):
        fault=dict(self.parts)
        fault['obstruction']=box(-35,-42,10,-29,-40,14)
        with self.assertRaisesRegex(AssertionError,'PMS tie path obstructed'):
            validate_modular_assembly(fault,self.refs)

    def test_blocked_gas_floor_slot_is_rejected(self):
        fault=dict(self.parts)
        fault['bottom']=fault['bottom'].union(box(16,-27,0,22,1,3))
        with self.assertRaisesRegex(AssertionError,'Bottom gas aperture obstructed'):
            validate_bottom_ventilation(fault,self.refs)

    def test_blocked_gas_baffle_exit_is_rejected(self):
        fault=dict(self.parts)
        fault['gas-splash-cover']=fault['gas-splash-cover'].union(box(21,-39,9,41,-37.9,27))
        with self.assertRaisesRegex(AssertionError,'Gas baffle exit obstructed'):
            validate_bottom_ventilation(fault,self.refs)

    def test_missing_gas_splash_cover_is_rejected(self):
        fault=dict(self.parts)
        fault['gas-splash-cover']=fault['gas-splash-cover'].cut(box(17,-24,25,21,-3,30))
        with self.assertRaisesRegex(AssertionError,'Gas splash cover missing'):
            validate_bottom_ventilation(fault,self.refs)

    def test_blocked_gas_riser_is_rejected(self):
        fault=dict(self.parts)
        fault['obstruction']=box(10,-26,65,11,-20,68)
        with self.assertRaisesRegex(AssertionError,'Gas chamber passage obstructed'):
            validate_bottom_ventilation(fault,self.refs)

    def test_pms_overlap_with_board_is_rejected(self):
        fault=dict(self.refs)
        fault['pms5003']=fault['pms5003'].translate((0,13,0))
        with self.assertRaisesRegex(AssertionError,'PMS collides with electronics'):
            validate_sensor_packing(fault)

    def test_pms_rotation_is_rejected(self):
        fault=dict(self.refs)
        fault['pms5003']=fault['pms5003'].rotate((0,0,0),(0,0,1),90)
        with self.assertRaisesRegex(AssertionError,'PMS orientation'):
            validate_sensor_packing(fault)

    def test_solid_retainer_face_is_rejected(self):
        fault=dict(self.parts)
        fault['cell-retainer']=fault['cell-retainer'].union(cy(-21,-24,106,15,2.5))
        with self.assertRaisesRegex(AssertionError,'Gas membrane obstructed'):
            validate_air_paths(fault)

    def test_blocked_pm_duct_is_rejected(self):
        fault=dict(self.parts)
        fault['bottom']=fault['bottom'].union(box(-45,-33,0,-22,-12,3))
        with self.assertRaisesRegex(AssertionError,'PMS air path obstructed'):
            validate_air_paths(fault)

    def test_blocked_exhaust_extension_is_rejected(self):
        fault=dict(self.parts)
        fault['pms-exhaust-extension']=fault['pms-exhaust-extension'].union(box(-22.5,-36,-25,8,-9,-23))
        with self.assertRaisesRegex(AssertionError,'PMS air path obstructed'):
            validate_air_paths(fault)

    def test_keyhole_obstruction_is_rejected(self):
        fault=dict(self.parts)
        fault['hood']=fault['hood'].union(box(-3,39.4,39,3,47,42))
        with self.assertRaisesRegex(AssertionError,'M4 sliding path obstructed'):
            validate_mount_and_service(fault)

    def test_missing_pocket_shield_is_rejected(self):
        fault=dict(self.parts)
        fault['hood']=fault['hood'].cut(box(-3,36,36,3,40,44))
        with self.assertRaisesRegex(AssertionError,'Mount pocket opens into sensor chamber'):
            validate_mount_and_service(fault)

    def test_missing_head_retention_is_rejected(self):
        fault=dict(self.parts)
        fault['hood']=fault['hood'].cut(cy(0,43.6,45,4.6,5))
        with self.assertRaisesRegex(AssertionError,'Keyhole does not retain the head'):
            validate_mount_and_service(fault)

if __name__=='__main__':unittest.main()
