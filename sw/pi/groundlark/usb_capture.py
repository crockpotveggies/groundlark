"""Standalone USB-head capture through the shared receiver and recording format."""
import sys
import time
from .recording import Writer
from .session import Sessions
from .transport import Receiver


def capture(args, factory=None, clock=time.monotonic_ns, sleep=time.sleep):
    if factory is None:
        if not sys.platform.startswith('linux'): raise ValueError('USB capture requires Linux')
        from .live import USB
        factory=USB
    if not 0 < args.seconds <= 3600 or not 1 <= args.max_mib <= 64:
        raise ValueError('USB capture bounds: 0..3600 seconds, 1..64 MiB')
    receiver=Receiver(Sessions(),board=3 if args.board=='skylark' else 2)
    usb=factory(args.usb,receiver)
    try:
        with open(args.output,'xb') as stream:
            writer=Writer(stream,dict(format='groundlark-acquisition-v1',source='usb-cdc',board=args.board,
                calibrations=[],timing='MCU acquisition clock; arrival is host monotonic; correlation unknown'),
                max_bytes=args.max_mib*1024*1024)
            end=clock()+int(args.seconds*1e9)
            while clock()<end:
                usb.poll(clock(),writer.message,writer.event);sleep(.001)
            writer.event('acquisition_summary','USB capture window completed',clock(),transport_errors=dict(receiver.errors))
    finally: usb.close()
    from .cli import replay
    return replay(args.output)
