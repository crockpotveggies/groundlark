"""Check real NiceGUI scene objects without launching a browser or acquisition."""
import unittest
from nicegui import ui
from geophone_scene import add_geophone


class GeophoneSceneTests(unittest.TestCase):
    def test_body_scale_pick_targets_and_adc_highlight_are_preserved(self):
        with ui.scene() as scene:
            adc=scene.ring(.72,.78,48)
            rings={9:[adc]};targets={adc.id:9}
            add_geophone(scene,(-2.8,-2.3),targets,rings,'#44d9c2')
        objects={obj.name:obj for obj in scene.objects.values() if obj.name}
        body=objects['geophone-body']
        self.assertEqual(body.args[:3],[1.27,1.27,3.3])
        self.assertEqual(targets[body.id],9)
        self.assertEqual(targets[objects['geophone-cap'].id],9)
        self.assertEqual(len(rings[9]),2)
        self.assertIs(rings[9][0],adc)
        self.assertEqual(targets[rings[9][1].id],9)
        leads=[obj for obj in scene.objects.values() if obj.name=='geophone-lead']
        self.assertEqual(len(leads),2)
        self.assertTrue(all(abs(obj.args[2][1]+3.1)<1e-9 for obj in leads))
        self.assertTrue(all(obj.args[1][2]==obj.args[2][2]==.52 for obj in leads))
        self.assertAlmostEqual(leads[1].args[2][0]-leads[0].args[2][0],.381)
        scene.delete()


if __name__=='__main__':unittest.main()
