"""Independent reference fixtures and calibration failure boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from groundlark import messages as m
from groundlark.calibration import Calibrations, canonical
from groundlark.calibration_fit import fit, observe, write_fit
from groundlark.recording import Writer
from groundlark.session import Sessions
from groundlark.simulation import defaults


class CalibrationFitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = next(c for c in defaults() if c['sensor_id'] == 9)
        self.spec = dict(version=1, device_id='fixture', sensor_id=9,
                         provenance='Independent synthetic voltage fixture', conditions='simulated 23 C',
                         fields={'geophone_input_v': dict(max_stddev_counts=[1], max_residual_si=[1e-8], observations=[])})
        # Independent transfer: count = input_volts * 1000000 + 17.
        for i, volts in enumerate([-.01, 0, .01]):
            name = f'p{i}.ssrec'
            self.record(name, round(volts * 1000000) + 17)
            self.spec['fields']['geophone_input_v']['observations'].append(dict(
                recording=name, first_sequence=0, last_sequence=31,
                reference_si=[volts], reference_uncertainty_si=[1e-6]))

    def record(self, name, count, *, device='fixture', boot=1, quality=1,
               dropped=0, cfg=None, complete=True, noise=False):
        with (self.root / name).open('wb') as stream:
            w = Writer(stream, dict(format='groundlark-acquisition-v1', source='simulation'))
            w.message(m.identity(device, boot, 1, [9]), 0)
            w.message(m.configuration(device, boot, [cfg or self.cfg]), 0)
            for i in range(32):
                w.message(m.batch(device, boot, 9, i, i,
                                  None if quality == 2 else dict(counts=count + (i % 2 * 20 if noise else 0), conversion_counter=i), quality=quality,
                                  dropped=dropped), i)
            if complete: w.event('acquisition_summary', 'fixture completed', 33)

    def fitted(self): return fit(self.spec, self.root, True)

    def test_known_transfer_identity_evidence_and_raw_preserved(self):
        record, evidence = self.fitted()
        c = record['fields']['geophone_input_v']
        self.assertAlmostEqual(c['scale'][0], 1e-6)
        self.assertAlmostEqual(c['offset'][0], -17e-6)
        self.assertEqual(record['evidence_sha256'], hashlib.sha256(canonical(evidence)).hexdigest())
        calibrations = Calibrations([record]); ident = next(iter(calibrations.records))
        cfg = m.configuration('fixture', 77, [self.cfg]).configuration.sensors[0]
        raw = m.batch('fixture', 77, 9, 0, 0, dict(counts=1017, conversion_counter=0))
        original = raw.SerializeToString()
        calibrated = calibrations.apply(raw, ident, cfg)
        self.assertAlmostEqual(calibrated.batch.samples[0].calibrated.geophone_input_v, .001)
        self.assertEqual(calibrated.batch.samples[0].geophone.counts, 1017)
        self.assertEqual(raw.SerializeToString(), original)
        sessions = Sessions(calibrations)
        sessions.accept(m.identity('fixture', 77, 1, [9]))
        sessions.accept(m.configuration('fixture', 77, [self.cfg]))
        sessions.accept(calibrated)
        other = deepcopy(calibrated); other.device_id = 'other'
        sessions.accept(m.identity('other', 77, 1, [9]))
        sessions.accept(m.configuration('other', 77, [self.cfg]))
        with self.assertRaisesRegex(ValueError, 'device'): sessions.accept(other)
        with self.assertRaisesRegex(ValueError, 'device'): calibrations.apply(other, ident, cfg)

    def test_out_of_range_and_missing_have_no_derived_value(self):
        record, _ = self.fitted(); c = Calibrations([record]); ident = next(iter(c.records))
        cfg = m.configuration('fixture', 1, [self.cfg]).configuration.sensors[0]
        for raw in (dict(counts=20000, conversion_counter=0), None):
            msg = m.batch('fixture', 1, 9, 0, 0, raw)
            self.assertFalse(c.apply(msg, ident, cfg).batch.samples[0].HasField('calibrated'))

    def test_write_evidence_and_refuse_overwrite(self):
        p = self.root / 'fit.json'; p.write_text(json.dumps(self.spec))
        out = self.root / 'cal.json'
        result = write_fit(p, out, True)
        self.assertTrue(result['simulation'])
        self.assertEqual(json.loads(out.read_text())[0]['device_id'], 'fixture')
        self.assertTrue(Path(result['evidence']).exists())
        with self.assertRaises(ValueError): write_fit(p, out, True)

    def test_simulation_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, 'simulation'): fit(self.spec, self.root)

    def test_faults_saturation_unknown_loss_and_incomplete_capture_rejected(self):
        for changes in [dict(quality=2), dict(quality=3), dict(quality=4), dict(dropped=None), dict(complete=False)]:
            with self.subTest(changes=changes):
                self.record('p0.ssrec', -9983, **changes)
                with self.assertRaises(ValueError): self.fitted()

    def test_wrong_device_and_changed_configuration_rejected(self):
        self.record('p0.ssrec', -9983, device='another')
        with self.assertRaisesRegex(ValueError, 'incomplete'): self.fitted()
        self.record('p0.ssrec', -9983)
        record, _ = self.fitted(); c = Calibrations([record])
        cfg = m.configuration('fixture', 1, [self.cfg]).configuration.sensors[0]
        cfg.geophone_gain = 32
        with self.assertRaisesRegex(ValueError, 'configuration'):
            c.verify(next(iter(c.records)), 9, cfg, 'fixture')

    def test_noise_residual_and_unfilled_limits_rejected(self):
        self.record('p0.ssrec', -9983, noise=True)
        with self.assertRaisesRegex(ValueError, 'stability'): self.fitted()
        self.record('p0.ssrec', -9983)
        self.record('p1.ssrec', 1000)
        with self.assertRaisesRegex(ValueError, 'residual'): self.fitted()
        self.spec['fields']['geophone_input_v']['max_stddev_counts'] = None
        with self.assertRaises(ValueError): self.fitted()

    def test_overlap_zero_span_and_nonfinite_references_rejected(self):
        points = self.spec['fields']['geophone_input_v']['observations']
        points[1]['recording'] = 'p0.ssrec'
        with self.assertRaisesRegex(ValueError, 'overlap'): self.fitted()
        points[1]['recording'] = 'p1.ssrec'
        for point in points: point['reference_si'] = [0]
        with self.assertRaises(ValueError): self.fitted()
        points[0]['reference_si'] = [float('nan')]
        with self.assertRaises(ValueError): self.fitted()

    def test_short_or_missing_interval_rejected(self):
        for first, last in [(0, 15), (0, 63), (1, 32)]:
            with self.assertRaises(ValueError):
                observe(self.root/'p0.ssrec', 'fixture', 9, 'geophone_input_v', first, last, True)

    def test_imu_six_faces_fit_each_package_axis(self):
        cfg = defaults()[0]
        points = []
        for index, reference in enumerate([(10,0,0),(-10,0,0),(0,10,0),(0,-10,0),(0,0,10),(0,0,-10)]):
            name = f'face{index}.ssrec'
            # Each axis has a different known count scale and bias.
            raw = tuple(round(v * scale + bias) for v, scale, bias in zip(reference, (100,200,400), (5,-7,11)))
            with (self.root/name).open('wb') as stream:
                w = Writer(stream, dict(format='groundlark-acquisition-v1', source='simulation'))
                w.message(m.identity('fixture', 1, 1, [1]), 0)
                w.message(m.configuration('fixture', 1, [cfg]), 0)
                for i in range(32): w.message(m.batch('fixture', 1, 1, i, i, dict(acceleration=raw, angular_rate=(0,0,0))), i)
                w.event('acquisition_summary', 'done', 33)
            points.append(dict(recording=name, first_sequence=0, last_sequence=31,
                               reference_si=list(reference), reference_uncertainty_si=[.001]*3))
        self.spec.update(sensor_id=1, fields={'acceleration_m_s2': dict(max_stddev_counts=[1]*3,
                        max_residual_si=[1e-9]*3, observations=points)})
        record, _ = self.fitted()
        coeff = record['fields']['acceleration_m_s2']
        for a, b in zip(coeff['scale'], [.01,.005,.0025]): self.assertAlmostEqual(a,b)
        for a, b in zip(coeff['offset'], [-.05,.035,-.0275]): self.assertAlmostEqual(a,b)


if __name__ == '__main__': unittest.main()
