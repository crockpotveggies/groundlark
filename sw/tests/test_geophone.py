"""Independent wire fixtures, loss faults, contract limits and response checks."""
import math
import unittest
from groundlark.geophone import ADS122C04, SETTINGS
from groundlark.sensors import NotReady
from groundlark import messages
from groundlark.simulation import defaults, Simulated
from groundlark.stimulus import Scenario
from groundlark_contract.validation import validate


class WireBus:
    def __init__(self):
        self.regs=[0]*4;self.counter=0;self.word=0;self.corrupt=False;self.short=False;self.ready=True
        self.writes=[];self.bad_register=False

    def exchange(self,address,write,count):
        assert address==0x40
        self.writes.append(bytes(write));op=write[0]
        if op==6:self.regs=[0]*4;return b''
        if op==8:return b''
        if op in (0x40,0x44,0x48,0x4c):self.regs[(op-0x40)//4]=write[1];return b''
        if op in (0x20,0x24,0x28,0x2c):
            i=(op-0x20)//4;v=self.regs[i]
            if i==2 and self.ready and self.regs[2]:v|=128
            if self.bad_register and i==0:v^=1
            data=bytes([v]);return data+bytes([v^255]) if self.regs[2]&16 else data
        assert op==16
        # Fixed-width signed wire encoding, independent of production decoder.
        v=self.word & 0xffffff
        data=bytes([self.counter,(v>>16)&255,(v>>8)&255,v&255])
        result=data+bytes(b^255 for b in data)
        if self.corrupt:result=result[:-1]+bytes([result[-1]^1])
        return result[:-1] if self.short else result

    def close(self):pass


class GeophoneTests(unittest.TestCase):
    def driver(self):
        bus=WireBus();now=[0.];driver=ADS122C04(bus,sleep=lambda _:None,clock=lambda:now[0])
        self.assertEqual(driver.configure(SETTINGS),SETTINGS)
        self.assertEqual(bus.regs,[12,136,80,0])
        self.assertIn(bytes.fromhex('4850'),bus.writes)
        return driver,bus,now

    def test_config_readback_and_wrong_profile_rejected(self):
        d,b,_=self.driver();b.bad_register=True
        with self.assertRaises(OSError):d.configure(SETTINGS)
        with self.assertRaises(ValueError):d.configure(dict(SETTINGS,geophone_gain=128))

    def test_signed_counts_and_counter_wrap(self):
        d,b,t=self.driver()
        for counter,count in ((254,-123456),(255,123456),(0,-1),(1,0)):
            b.counter,b.word=counter,count;t[0]+=.0031
            r=d.read();self.assertEqual(r.raw,dict(counts=count,conversion_counter=counter));self.assertEqual(r.quality,1)

    def test_endpoints_mark_saturation(self):
        for word in (-8388608,8388607):
            d,b,_=self.driver();b.word=word
            self.assertEqual(d.read().quality,3)

    def test_crc_equivalent_inversion_short_read_and_gap_rejected(self):
        for fault in ('corrupt','short'):
            d,b,_=self.driver();setattr(b,fault,True)
            with self.assertRaises(OSError):d.read()
        d,b,t=self.driver();d.read();b.counter=3;t[0]=.01
        with self.assertRaisesRegex(OSError,'gap'):d.read()
        b.counter=4;t[0]=.014;self.assertEqual(d.read().raw['conversion_counter'],4)

    def test_not_ready_duplicate_and_ambiguous_wrap(self):
        d,b,t=self.driver();b.ready=False
        with self.assertRaises(NotReady):d.read()
        b.ready=True;d.read();t[0]=.001
        with self.assertRaises(NotReady):d.read()
        b.counter=1;t[0]=1
        with self.assertRaisesRegex(OSError,'ambiguous'):d.read()

    def test_contract_cannot_relabel_adc_as_gnss_or_remote_clock(self):
        m=messages.batch('daqhat-01',1,9,0,1,dict(counts=0,conversion_counter=0),dropped=None)
        self.assertEqual(m.batch.samples[0].time.domain,1)
        m.batch.samples[0].time.domain=2
        with self.assertRaises(ValueError):validate(m)
        m.batch.samples[0].time.domain=1;m.batch.samples[0].geophone.counts=8388608
        with self.assertRaises(ValueError):validate(m)
        self.assertEqual([s['sensor_id'] for s in defaults()],[1,2,3,9,6])
        self.assertEqual(defaults(legacy_gnss=True)[-1]['sensor_id'],6)

    def test_duplicate_polls_cannot_hide_a_full_counter_rollover(self):
        d,b,t=self.driver();d.read()
        for at in (.1,.2,.3,.4,.5,.6):
            t[0]=at
            with self.assertRaises(NotReady):d.read()
        # 257 conversions can look like a single increment after a stalled bus.
        t[0]=.781;b.counter=1
        with self.assertRaisesRegex(OSError,'ambiguous'):d.read()
        t[0]=.785;b.counter=2
        self.assertEqual(d.read().raw['conversion_counter'],2)

    def test_resonance_dc_and_low_frequency_attenuation(self):
        def peak(f):
            scenario=Scenario(dict(version=1,initial={'geophone_velocity_m_s':{'amplitude':.0001,'frequency_hz':f}}))
            return max(abs(Simulated(9,scenario=scenario,clock=lambda n=n:round(n/f*1e9/1000)).read().raw['counts']) for n in range(1000))
        self.assertEqual(Simulated(9,scenario=Scenario(dict(version=1,initial={'geophone_velocity_m_s':1}))).read().raw['counts'],0)
        # Independent Racotech response at resonance: sensitivity / (2*zeta).
        self.assertAlmostEqual(peak(4.5)/(23.4*.0001/.032*8388608),1/1.4,delta=.002)
        self.assertLess(peak(.5)/peak(10),.014)
        self.assertAlmostEqual(peak(10),602776,delta=5)
