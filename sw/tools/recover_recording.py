"""Copy a CRC-valid recording prefix; never edit the interrupted original."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'pi'),str(Path(__file__).resolve().parents[1]/'interfaces/python')]
from groundlark.recording import Reader, RecordingError
from groundlark.session import Sessions
from groundlark.calibration import Calibrations


def recover(source, target):
    source, target=Path(source),Path(target)
    with source.open('rb') as stream:
        reader=Reader(stream)  # Refuse a damaged header; do not guess metadata.
        sessions=Sessions(Calibrations(reader.metadata.get('calibrations',[])),
                          checkpoint=reader.metadata.get('session_checkpoint'))
        end=stream.tell(); count=0; error=None
        try:
            for _,item in reader:
                if isinstance(item,dict):
                    if item.get('code')=='usb_disconnected':sessions.disconnect(item.get('device'))
                else:sessions.accept(item)
                end=stream.tell(); count+=1
        except (RecordingError,ValueError) as fault: error=str(fault)
        stream.seek(0)
        with target.open('xb') as out:
            remaining=end
            while remaining:
                chunk=stream.read(min(65536,remaining))
                if not chunk: raise OSError('source changed during recovery')
                out.write(chunk);remaining-=len(chunk)
    with source.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(records=count,valid_prefix_bytes=end,error=error,
                source_sha256=digest,
                completion='unchanged; recovery does not append a completion marker')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('target')
    args=p.parse_args();print(json.dumps(recover(args.source,args.target),indent=2))
