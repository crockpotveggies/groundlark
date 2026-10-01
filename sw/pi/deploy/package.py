"""Create a checksummed source/runtime bundle; generated output stays local."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[3]


def package(output):
    output=Path(output)
    if output.exists(): raise FileExistsError(output)
    with tempfile.TemporaryDirectory() as temporary:
        staging=Path(temporary)
        tracked=subprocess.check_output(['git','ls-files','-z','sw','LICENSE'],cwd=ROOT).decode().split('\0')
        # Include newly authored files while still excluding ignored build/cache output.
        tracked+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z','sw'],cwd=ROOT).decode().split('\0')
        # The UI verifies the provenance of its board views at startup.
        for provenance in (ROOT/'sw/ui/assets').glob('*provenance*.json'):
            tracked+=list(json.loads(provenance.read_text(encoding='utf8')).get('sha256',{}))
        paths=sorted({name for name in tracked if name and (ROOT/name).is_file()})
        for name in paths:
            target=staging/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        schema=ROOT/'sw/build/schema.binpb'
        if not schema.is_file():raise ValueError('Build and validate the current descriptor first')
        target=staging/'sw/build/schema.binpb';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(schema.read_bytes())
        paths.append('sw/build/schema.binpb')
        (staging/'SHA256SUMS').write_text(''.join(hashlib.sha256((staging/p).read_bytes()).hexdigest()+'  '+p+'\n' for p in sorted(paths)),encoding='utf8')
        output.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(output,'w') as archive:
            for path in sorted(staging.rglob('*')):
                if not path.is_file():continue
                info=archive.gettarinfo(str(path),arcname=path.relative_to(staging).as_posix())
                info.mtime=0;info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o644
                with path.open('rb') as stream:archive.addfile(info,stream)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    package(parser.parse_args().output)
