"""Run Burrowlark production C and decode with the independent v1 receiver."""
from pathlib import Path
import subprocess
import sys
import unittest
from groundlark.messages import Envelope
from groundlark.session import Sessions
from groundlark_contract.framing import Decoder

ROOT=Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform.startswith('linux'),'native C runs in the portable software profile')
class HeadFirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.program=ROOT/'sw/build/head-native'
        cls.program.parent.mkdir(parents=True,exist_ok=True)
        fw=ROOT/'sw/field-head/firmware'
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                        '-I'+str(fw),str(fw/'head.c'),str(ROOT/'sw/field-head/tests/native.c'),'-o',str(cls.program)],check=True)

    def capture(self,mode):
        result=subprocess.run([str(self.program),str(mode)],capture_output=True,check=True,timeout=10)
        decoder=Decoder();session=Sessions();messages=[]
        for start in range(0,len(result.stdout),37):
            for payload in decoder.feed(result.stdout[start:start+37]):
                m=Envelope().FromString(payload);session.accept(m);messages.append(m)
        self.assertEqual(decoder.errors,0)
        return messages

    def test_inventory_signed_axes_and_crc(self):
        messages=self.capture(0)
        self.assertEqual(list(messages[0].identity.sensors),[7,17])
        samples=[(m.batch.sensor_id,s) for m in messages if m.WhichOneof('body')=='batch' for s in m.batch.samples]
        mag=[s for sid,s in samples if sid==7]
        self.assertEqual((mag[0].magnetic.counts.x,mag[0].magnetic.counts.y,mag[0].magnetic.counts.z),(-2,0,8388606))
        self.assertTrue(any(s.quality==1 for sid,s in samples if sid==17))
        self.assertTrue(all(s.time.domain==2 and not s.time.HasField('utc_unix_ns') for _,s in samples))

    def test_suspend_during_configuration_cannot_publish_stale_data(self):
        self.assertEqual(self.capture(6),[])

    def test_boot_journal_uses_f042_one_kib_pages_under_power_cuts(self):
        output=ROOT/'sw/build/head-boot-native'
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',
            '-DBOOT_PAGE_WORDS=256','-DTEST_PAGE_WORDS=256','-I'+str(ROOT/'sw/skylark/firmware'),
            str(ROOT/'sw/skylark/firmware/boot.c'),str(ROOT/'sw/skylark/tests/boot.c'),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True,timeout=10)

    def test_faults_disconnect_suspend_and_backpressure(self):
        for mode in range(1,6):
            with self.subTest(mode=mode):
                messages=self.capture(mode)
                batches=[m.batch for m in messages if m.WhichOneof('body')=='batch']
                self.assertTrue(batches)
                self.assertTrue(all(not b.HasField('dropped_before') for b in batches))
                if mode in (1,2):self.assertTrue(any(s.quality==2 for b in batches for s in b.samples))
                if mode in (3,4):self.assertGreater(len([m for m in messages if m.WhichOneof('body')=='identity']),1)
                if mode==5:
                    self.assertTrue(any(m.WhichOneof('body')=='status' and m.status.code==4 for m in messages))
                    seq=[s.sequence for b in batches if b.sensor_id==7 for s in b.samples]
                    self.assertTrue(any(b>a+1 for a,b in zip(seq,seq[1:])))
