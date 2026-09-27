"""Build the pinned STM32 support library when constructing the lab image."""
import hashlib
from io import BytesIO
from pathlib import Path
import subprocess
import tarfile
from urllib.request import urlopen

COMMIT='2da12dc96e0b9e42a3332348dd9b02a0a17981f8'
SHA256='b1003f8b08bc722855e756141b02c7648178142928ace844e72911596770a21d'
TARGET=Path('/opt/skylark/libopencm3')


def main():
    with urlopen(f'https://codeload.github.com/libopencm3/libopencm3/tar.gz/{COMMIT}',timeout=60) as response:
        data=response.read(8*1024*1024)
    if hashlib.sha256(data).hexdigest()!=SHA256:raise RuntimeError('libopencm3 archive checksum')
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=BytesIO(data),mode='r:gz') as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):raise RuntimeError('Unexpected archive entry')
            if '..' in Path(member.name).parts or Path(member.name).parts[0]!=f'libopencm3-{COMMIT}':raise RuntimeError('Archive path')
        archive.extractall(TARGET.parent,filter='data')
    (TARGET.parent/f'libopencm3-{COMMIT}').rename(TARGET)
    subprocess.run(['make','-j4','TARGETS=stm32/f0','CFLAGS=-Os -isystem/usr/include/newlib'],cwd=TARGET,check=True)
    # Keep complete upstream sources and licenses with the toolchain.
    (TARGET.parent/'revision.txt').write_text(f'{COMMIT}\n{SHA256}\n')


if __name__=='__main__':main()
