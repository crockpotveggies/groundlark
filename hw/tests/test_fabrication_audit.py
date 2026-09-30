import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fabrication_audit import standard_process_issues


class FabricationProcessTests(unittest.TestCase):
    def setUp(self):
        self.profile = dict(copper_layers=6, thickness_mm=1.6, size_mm=[140, 56],
                            stack_copper_layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'],
                            tracks_by_layer={'F.Cu':1},
                            ground_planes=['In1.Cu', 'In4.Cu'],
                            vias=[dict(type='through', span=['F.Cu', 'B.Cu'],
                                       drill_mm=.3, pad_mm=.45)])

    def test_conventional_process(self):
        self.assertEqual(standard_process_issues(self.profile), [])

    def test_hidden_microvia_is_not_a_standard_through_via(self):
        for kind in ('microvia', 'blind/buried'):
            profile = copy.deepcopy(self.profile)
            profile['vias'].append(dict(type=kind, span=['F.Cu', 'In1.Cu'],
                                        drill_mm=.3, pad_mm=.45))
            self.assertTrue(standard_process_issues(profile))

    def test_span_is_checked_independently_of_type(self):
        self.profile['vias'][0]['span'] = ['In1.Cu', 'In4.Cu']
        self.assertTrue(standard_process_issues(self.profile))

    def test_small_drill_triggers_cost_profile_failure(self):
        self.profile['vias'][0]['drill_mm'] = .2
        self.assertTrue(standard_process_issues(self.profile))

    def test_oversized_drill_cannot_hide_thin_annular_ring(self):
        self.profile['vias'][0]['drill_mm'] = .35
        self.assertTrue(standard_process_issues(self.profile))

    def test_missing_vias_cannot_pass(self):
        self.profile['vias'] = []
        self.assertTrue(standard_process_issues(self.profile))

    def test_disabled_copper_cannot_hide_behind_layer_count(self):
        self.profile['tracks_by_layer']['In6.Cu']=1
        self.assertTrue(standard_process_issues(self.profile))

    def test_stale_serialized_stack_is_rejected(self):
        self.profile['stack_copper_layers'].insert(-1,'In5.Cu')
        self.assertTrue(standard_process_issues(self.profile))

    def test_wrong_layer_count_or_missing_reference_plane(self):
        for key, value in [('copper_layers', 8), ('ground_planes', ['In1.Cu']),
                           ('thickness_mm', 1.2), ('size_mm', [90, 56])]:
            with self.subTest(key=key):
                profile = copy.deepcopy(self.profile)
                profile[key] = value
                self.assertTrue(standard_process_issues(profile))


if __name__ == '__main__':
    unittest.main()
