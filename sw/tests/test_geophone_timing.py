"""Free-running ADC, four-channel scheduler and bounded bus-latency stress.

The conversion clock advances independently of reads. This is deterministic
fault injection, not a Pi throughput benchmark or an emulation of its kernel.
"""
import io
import json
from pathlib import Path
import unittest
from groundlark.geophone import ADS122C04
from groundlark.recording import Writer, Reader
from groundlark.runtime import Acquisition, Channel
from groundlark.session import Sessions
from groundlark.simulation import defaults
from groundlark.stimulus import Scenario
from groundlark.virtual_hat import VirtualDriver


class Clock:
    ns = 0
    def __call__(self): return self.ns
    def advance(self, ns): self.ns += round(ns)


class ClockedADC:
    def __init__(self, clock, hz=100_000, oscillator=1):
        self.clock, self.hz, self.oscillator = clock, hz, oscillator
        self.regs, self.start, self.last = [0]*4, None, -1
        self.frames = []

    def generation(self):
        if self.start is None: return 0
        # TI Table 12, 3116 clocks/conversion; not 1/nominal 330 SPS.
        return max(0, int((self.clock()-self.start)*1.024e6*self.oscillator/(3116*1e9)))

    def exchange(self, address, write, count):
        assert address == 0x40
        op, generation = write[0], self.generation()
        # Include ACK bits and both slave addresses in a combined transaction.
        self.clock.advance((1+len(write)+(1+count if count else 0))*9e9/self.hz)
        if op == 6: self.regs, self.start, self.last = [0]*4, None, -1; return b''
        if op == 8: self.start = self.clock(); return b''
        if op & 0xf0 == 0x40:
            self.regs[(op >> 2) & 3] = write[1]; return b''
        if op & 0xf0 == 0x20:
            i=(op >> 2) & 3
            v=self.regs[i] | (128 if i == 2 and generation > 0 and generation != self.last else 0)
            data=bytes([v])
        else:
            assert op == 16 and generation > 0
            self.last=generation
            self.frames.append((generation,self.clock()))
            # Generation itself is an independent, traceable signal fixture.
            data=bytes([generation & 255])+generation.to_bytes(3,'big',signed=True)
        return data+bytes(v^255 for v in data) if self.regs[2]&16 else data

    def close(self): pass


class DelayedSensor:
    def __init__(self, sensor, clock):
        self.clock=clock
        self.device=VirtualDriver(sensor,Scenario(),clock)
        self.delay=150_000 if sensor <= 4 else 500_000
    def configure(self,cfg): return self.device.configure(cfg)
    def read(self):
        self.clock.advance(self.delay)
        return self.device.read()
    def close(self): self.device.close()


def exercise(hz=100_000, oscillator=1, stalls=()):
    clock=Clock();bus=ClockedADC(clock,hz,oscillator)
    adc=ADS122C04(bus,sleep=lambda s:clock.advance(s*1e9),clock=lambda:clock()/1e9)
    channels=[Channel('stress-pi',1,cfg,adc if cfg['sensor_id']==9 else DelayedSensor(cfg['sensor_id'],clock)) for cfg in defaults()]
    stream=io.BytesIO();app=Acquisition(Writer(stream,{}),Sessions(),channels,capacity=64)
    app.start(clock());start=clock();end=start+3_000_000_000;pending=list(stalls)
    while clock()<end:
        if pending and clock()-start >= pending[0][0]:
            clock.advance(pending.pop(0)[1])
        app.tick(clock);app.drain();clock.advance(1_000_000)
    app.finish(clock());app.close();stream.seek(0)
    items=[item for _,item in Reader(stream) if not isinstance(item,dict)]
    batches=[m.batch for m in items if m.WhichOneof('body')=='batch' and m.batch.sensor_id==9]
    valid=[s for b in batches for s in b.samples if s.quality in (1,3)]
    statuses=[m.status.detail for m in items if m.WhichOneof('body')=='status' and m.status.sensor_id==9]
    frames=set(bus.frames)
    for sample in valid:
        assert sample.geophone.counts & 255 == sample.geophone.conversion_counter
        assert (sample.geophone.counts,sample.time.acquisition_ns) in frames
        assert not sample.time.HasField('uncertainty_ns')
    assert all(not b.HasField('dropped_before') for b in batches)
    assert all(a.time.acquisition_ns < b.time.acquisition_ns for a,b in zip(valid,valid[1:]))
    report=dict(bus_hz=hz,oscillator_ratio=oscillator,stalls=list(stalls),valid=len(valid),
                missing=sum(s.quality==2 for b in batches for s in b.samples),
                gaps=sum('conversion gap' in s for s in statuses),
                ambiguous=sum('interval ambiguous' in s for s in statuses),
                valid_hz=len(valid)/((clock()-start)/1e9),
                other_sensor_ids=sorted({m.batch.sensor_id for m in items if m.WhichOneof('body')=='batch'}),
                unknown_loss_preserved=True,completion_timestamps=True)
    report['recoveries']=app.recoveries
    report['offline']=any(c.offline for c in channels)
    return report


class GeophoneTimingTests(unittest.TestCase):
    def test_four_channels_clock_tolerance_and_bus_speed(self):
        rows=[]
        for hz in (100_000,400_000):
            for oscillator in (.98,1,1.02):
                row=exercise(hz,oscillator);rows.append(row)
                self.assertEqual(row['other_sensor_ids'],[1,2,3,6,9])
                self.assertGreater(row['valid'],300)
                self.assertEqual(row['ambiguous'],0)
                self.assertEqual(row['recoveries'],0)
                self.assertFalse(row['offline'])
        # A run with conversion gaps is evidence of lost service, not a throughput PASS.
        out=Path(__file__).resolve().parents[1]/'build'
        out.mkdir(exist_ok=True)
        (out/'acquisition-stress.json').write_text(json.dumps(dict(
            scope='deterministic four-channel model; no target Pi or real IPC benchmark',
            cases=rows,throughput_qualified=False),indent=2)+'\n')

    def test_delayed_service_and_full_wrap_are_visible_then_recover(self):
        short=exercise(stalls=((500_000_000,12_000_000),))
        long=exercise(stalls=((500_000_000,900_000_000),))
        self.assertGreater(short['gaps'],0)
        self.assertGreaterEqual(long['ambiguous'],1)
        self.assertGreater(long['valid'],200)
        self.assertEqual(long['recoveries'],0)
        self.assertFalse(long['offline'])

    def test_fast_and_slow_conversion_clocks_do_not_fabricate_exact_timing(self):
        for oscillator in (.98,1.02):
            row=exercise(oscillator=oscillator,stalls=((1_000_000_000,30_000_000),))
            self.assertTrue(row['unknown_loss_preserved'])
            self.assertTrue(row['completion_timestamps'])
            self.assertGreater(row['missing'],0)

