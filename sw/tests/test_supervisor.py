"""Native production state machine: no GPIO or battery qualification implied."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]

@unittest.skipUnless(sys.platform.startswith('linux'),'native C runs in portable lab')
class SupervisorTests(unittest.TestCase):
    def test_policy_voltage_acknowledgement_timeouts_and_week_disabled(self):
        fw=ROOT/'sw/supervisor/firmware';output=ROOT/'sw/build/supervisor-native'
        output.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(fw),str(fw/'power.c'),
                        str(ROOT/'sw/supervisor/tests/native.c'),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True,timeout=10)
