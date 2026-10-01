"""Standalone USB-head capture through the shared receiver and recording format."""
import sys
import time
from .recording import Writer
from .session import Sessions
from .transport import Receiver


def capture(args, factory=None, clock=time.monotonic_ns, sleep=time.sleep):
    service_writer = getattr(args, 'writer_factory', None)
    service_stop = getattr(args, 'stop_event', None)
    if factory is None:
        if not sys.platform.startswith('linux'): raise ValueError('USB capture requires Linux')
        from .live import USB
        factory=USB
    if (not service_writer and not 0 < args.seconds <= 3600) or not 1 <= args.max_mib <= 64:
        raise ValueError('USB capture bounds: 0..3600 seconds, 1..64 MiB')
    receiver=Receiver(Sessions(),board=3 if args.board=='skylark' else 2)
    usb=factory(args.usb,receiver)
    try:
        from contextlib import ExitStack
        with ExitStack() as stack:
            metadata=dict(format='groundlark-acquisition-v1',source='usb-cdc',board=args.board,
                calibrations=[],timing='MCU acquisition clock; arrival is host monotonic; correlation unknown')
            if service_writer:
                writer=service_writer(metadata)
                stack.callback(writer.close, False)
            else:
                stream=stack.enter_context(open(args.output,'xb'))
                writer=Writer(stream,metadata,max_bytes=args.max_mib*1024*1024)
            end=clock()+int(args.seconds*1e9)
            while (service_writer or clock()<end) and not (service_stop and service_stop.is_set()):
                usb.poll(clock(),writer.message,writer.event);sleep(.001)
                if service_writer:
                    writer.heartbeat()
                    if usb.fd is None and usb.attempts >= usb.retries:
                        raise OSError('USB reconnect budget exhausted; station cooldown required')
            writer.event('acquisition_summary','USB capture window completed',clock(),transport_errors=dict(receiver.errors))
            if service_writer: writer.close()
    finally: usb.close()
    if service_writer: return dict(stopped=True)
    from .cli import replay
    return replay(args.output)
