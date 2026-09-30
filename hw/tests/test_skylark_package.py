"""Procurement and export fault fixtures, independent of local release archives."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from skylark_package import BOARD_DIR, REGISTRY, MAPPINGS, BOARD, select, placement_inputs, export, sha
from jlcpcb_placement import correct_placements
from skylark_inspect import match


class ProcurementTests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads(REGISTRY.read_text())
        with (BOARD_DIR/'bom.csv').open(newline='',encoding='utf-8') as f:
            self.source=list(csv.DictReader(f))

    def test_complete_identity_and_manual_parts(self):
        selected=select(self.source,self.registry)
        self.assertEqual(len(selected),119)
        self.assertEqual((selected['C2']['mpn'],selected['C2']['jlcpcb_part']),('GRM21BR71C475KE51L','C408144'))
        self.assertEqual(selected['U11']['manufacturer'],'Sensirion')
        self.assertEqual(selected['U12']['mpn'],'BMP388')
        self.assertTrue(all(p['minimum_order_quantity']==1 and p['ordering_status']=='available' for p in self.registry['parts']))
        self.assertNotIn('GS1',selected)
        self.assertEqual(sum(p['quantity'] for p in self.registry['manual_parts'] if p['manufacturer']=='Mill-Max'),8)

    def test_stock_policy_rejects_preorders_moq_and_unallocated_stock(self):
        for key,bad in [('ordering_status','pre-order'),('minimum_order_quantity',2),
                        ('available_order_quantity',0),('stock',None)]:
            with self.subTest(key=key):
                registry=copy.deepcopy(self.registry)
                registry['parts'][0][key]=bad
                with self.assertRaisesRegex(ValueError,'Procurement policy'):
                    select(self.source,registry)

    def test_missing_reference_rejected(self):
        self.registry['parts'][0]['references'].pop()
        with self.assertRaisesRegex(ValueError,'coverage'): select(self.source,self.registry)

    def test_duplicate_reference_rejected(self):
        self.registry['parts'].append(copy.deepcopy(self.registry['parts'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'): select(self.source,self.registry)

    def test_footprint_change_rejected(self):
        next(r for r in self.source if r['Reference']=='U7')['Footprint']='SOIC8.kicad_mod'
        with self.assertRaisesRegex(ValueError,'binding'): select(self.source,self.registry)

    def test_undocumented_substitution_rejected(self):
        next(p for p in self.registry['parts'] if 'C2' in p['references']).pop('resolution')
        with self.assertRaisesRegex(ValueError,'substitution'): select(self.source,self.registry)

    def test_drill_comparison_detects_loss_duplicates_and_slot_length(self):
        expected=[(1.,2.,.3),(4.,5.,4.,6.1,.6)]
        match(expected,list(reversed(expected)))
        for actual in [expected[:-1],expected+expected[:1],[(1.,2.,.3),(4.,5.,4.,6.2,.6)]]:
            with self.assertRaises(ValueError): match(expected,actual)


@unittest.skipUnless(importlib.util.find_spec('pcbnew') and shutil.which('kicad-cli'),'KiCad Python/CLI required')
class PlacementTests(unittest.TestCase):
    def setUp(self):
        import pcbnew as p
        with (BOARD_DIR/'bom.csv').open(newline='',encoding='utf-8') as f: source=list(csv.DictReader(f))
        selections=select(source,json.loads(REGISTRY.read_text()))
        selections={r['Reference']:dict(selections[r['Reference']],native_footprint=r['Footprint']) for r in source if r['Reference'] in selections}
        self.rows,self.geo,self.selected=placement_inputs(p.LoadBoard(str(BOARD)),selections)
        self.maps=json.loads(MAPPINGS.read_text())

    def test_all_numbered_supplier_pads_fit(self):
        rows,audit=correct_placements(self.rows,self.geo,self.selected,self.maps)
        self.assertEqual([a['reference'] for a in audit if 'pads_checked' not in a],[])
        self.assertEqual(sum('pads_checked' in a for a in audit),119)
        byref={r['Designator']:r for r in rows}
        self.assertEqual(byref['J1']['Layer'],'Top') # HAT J1 is bottom; Skylark J1 is top.
        self.assertEqual(float(byref['U1']['Rotation']),180)
        self.assertEqual(float(byref['U6']['Rotation']),270)
        self.assertEqual(byref['U8']['Layer'],'Bottom')
        self.assertEqual(float(byref['U8']['Rotation']),270)

    def test_bottom_projection_required(self):
        next(e for e in self.maps['footprints'] if 'U8' in e['designators']).pop('bottom_projection')
        with self.assertRaisesRegex(ValueError,'bottom-side'): correct_placements(self.rows,self.geo,self.selected,self.maps)

    def test_supplier_pin_identity_fault_rejected(self):
        entry=next(e for e in self.maps['footprints'] if 'U1' in e['designators'])
        fields=entry['pad_shapes'][0].split('~'); fields[8]='999';entry['pad_shapes'][0]='~'.join(fields)
        with self.assertRaisesRegex(ValueError,'identities'): correct_placements(self.rows,self.geo,self.selected,self.maps)

    def test_sht_die_pad_is_deliberately_unsoldered(self):
        entry=next(e for e in self.maps['footprints'] if 'U11' in e['designators'])
        self.assertEqual({s.split('~')[8] for s in entry['pad_shapes']},{'1','2','3','4'})
        self.assertEqual([s.split('~')[8] for s in entry['excluded_noncontact_pads']],['5'])
        entry['pad_shapes']+=entry['excluded_noncontact_pads']
        with self.assertRaisesRegex(ValueError,'identities'): correct_placements(self.rows,self.geo,self.selected,self.maps)

    def test_readonly_full_export(self):
        before=sha(BOARD)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'package';manifest=export(out)
            self.assertEqual(manifest['physical_placements'],119)
            self.assertEqual(manifest['supplier_fitted_placements'],119)
            self.assertEqual(manifest['construction']['via_in_smt_pad'],0)
            self.assertFalse(manifest['construction']['filled_capped_vias_required'])
            self.assertFalse(any('UNVERIFIED' in h for h in manifest['holds']))
            self.assertEqual(len(list((out/'gerbers').glob('*.drl'))),2)
            for path,digest in manifest['files_sha256'].items():self.assertEqual(sha(out/path),digest)
            with (out/'BOM-review.csv').open() as f:bom=list(csv.DictReader(f))
            self.assertEqual(sum(len(r['Designator'].split(',')) for r in bom),119)
            self.assertFalse(any('GS1' in r['Designator'] for r in bom))
            if importlib.util.find_spec('gerbonara'):
                from skylark_inspect import inspect
                result=inspect(out)
                self.assertEqual(result['drills'],{'PTH':{'round':177,'slots':4},'NPTH':{'round':6,'slots':0}})
        self.assertEqual(sha(BOARD),before)


if __name__=='__main__':unittest.main()
