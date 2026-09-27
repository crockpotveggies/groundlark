"""Check exported gas-cell geometry and shared working/auxiliary selection."""
import json
from pathlib import Path
import struct
import unittest
from nicegui import ui
from skylark_scene import add_skylark


class SkylarkSceneTests(unittest.TestCase):
    def test_native_export_has_cell_clearance_and_correct_centres(self):
        raw=(Path(__file__).parent/'assets/skylark.glb').read_bytes()
        self.assertEqual(raw[:4],b'glTF')
        data=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
        for name,x in [('GS1-0',.074),('GS2-0',.116)]:
            node=next(n for n in data['nodes'] if n.get('name')==name)
            mesh=data['meshes'][node['mesh']]
            bounds=data['accessors'][mesh['primitives'][0]['attributes']['POSITION']]
            self.assertAlmostEqual(bounds['min'][0],x-.01575,places=6)
            self.assertAlmostEqual(bounds['max'][0],x+.01575,places=6)
            self.assertAlmostEqual(bounds['min'][1],.00729,places=6)
            self.assertAlmostEqual(bounds['max'][1],.02259,places=6)
            self.assertAlmostEqual((bounds['min'][2]+bounds['max'][2])/2,.079,places=6)

    def test_working_and_auxiliary_share_cell_highlight(self):
        targets,rings={},{}
        with ui.scene() as scene:board=add_skylark(scene,targets,rings,'#44d9c2')
        self.assertEqual(set(rings),set(range(10,17)))
        self.assertIs(rings[10][0],rings[11][0]);self.assertIs(rings[12][0],rings[13][0])
        self.assertEqual(set(targets.values()),{10,12,14,15,16})
        self.assertFalse(board.visible_)
        scene.delete()


if __name__=='__main__':unittest.main()
