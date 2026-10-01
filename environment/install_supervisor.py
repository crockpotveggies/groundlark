"""Fetch the pinned TI headers/driver sources when building the lab image."""
from pathlib import Path
import subprocess

COMMIT='20807db79aa17b49f87ab8ec87f6b6d63ee2cb32'
TARGET=Path('/opt/supervisor/mspm0-sdk')


def main():
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','clone','--filter=blob:none','--no-checkout',
                    'https://github.com/TexasInstruments/mspm0-sdk.git',str(TARGET)],check=True)
    def git(*args):subprocess.run(['git','-C',str(TARGET),*args],check=True)
    git('sparse-checkout','set','source/ti/devices','source/ti/driverlib','source/third_party/CMSIS')
    git('checkout','--detach',COMMIT)
    actual=subprocess.check_output(['git','-C',str(TARGET),'rev-parse','HEAD'],text=True).strip()
    if actual!=COMMIT:raise RuntimeError('TI SDK revision mismatch')
    (TARGET.parent/'revision.txt').write_text(COMMIT+'\n')


if __name__=='__main__':main()
