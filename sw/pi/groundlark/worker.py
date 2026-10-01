"""One outstanding call per worker, finite restart and bounded reap attempts."""
import multiprocessing as mp
from .sensors import NotReady, DataGap
from .fifo import FifoFault


def child(connection, factory, settings):
    device = None
    try:
        device = factory()
        connection.send(("ready", device.configure(settings)))
        while connection.recv() == "read":
            try: connection.send(("sample", device.read()))
            except FifoFault as error: connection.send(("fifo_error", str(error)[:160]))
            except NotReady as error: connection.send(("missing", str(error)[:160]))
            except DataGap as error: connection.send(("data_gap", str(error)[:160]))
            except (OSError, ValueError) as error: connection.send(("error", str(error)[:160]))
    except (EOFError, BrokenPipeError): pass
    except Exception as error:
        try: connection.send(("error", str(error)[:160]))
        except (BrokenPipeError, EOFError, OSError): pass
    finally:
        if device is not None and hasattr(device, "close"): device.close()
        connection.close()


class Worker:
    loss_unknown = True  # Polling cannot account for overwritten physical conversions.
    def __init__(self, factory, settings, timeout=.25, startup_timeout=4, restart_limit=2, irq=None):
        self.factory, self.settings = factory, settings
        self.timeout, self.startup_timeout, self.restart_limit = timeout, startup_timeout, restart_limit
        self.process = self.connection = None
        self.restarts, self.started = 0, False
        self.buffered = bool(getattr(factory, 'fifo', False) or getattr(factory, 'utc', False) or getattr(factory, 'drdy', None))
        self.irq = irq

    def ready(self): return self.irq is not None and self.irq.poll()

    def _stop(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.process is not None:
            if self.process.is_alive(): self.process.terminate()
            self.process.join(.1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(.1)
            if self.process.is_alive(): raise TimeoutError("unreaped worker; restart prohibited")
            self.process.close()
            self.process = None

    def _receive(self, seconds):
        try:
            if not self.connection.poll(seconds): raise TimeoutError("sensor worker deadline")
            return self.connection.recv()
        except (OSError, EOFError, TimeoutError):
            self._stop()
            raise TimeoutError("sensor worker unavailable or timed out")

    def configure(self, settings=None):
        if settings is not None: self.settings = settings
        self._stop()
        if self.started:
            if self.restarts >= self.restart_limit: raise OSError("sensor restart budget exhausted")
            self.restarts += 1
        self.started = True
        context = mp.get_context("spawn")
        self.connection, other = context.Pipe()
        self.process = context.Process(target=child, args=(other, self.factory, self.settings), daemon=True)
        self.process.start()
        other.close()
        kind, result = self._receive(self.startup_timeout)
        if kind != "ready":
            self._stop()
            raise OSError(result)
        return result

    def read(self):
        if self.connection is None: raise OSError("sensor worker offline")
        try: self.connection.send("read")
        except (OSError, EOFError):
            self._stop()
            raise OSError("sensor worker disconnected")
        kind, value = self._receive(self.timeout)
        if kind == "missing": raise NotReady(value)
        if kind == "data_gap": raise DataGap(value)
        if kind == "fifo_error": raise FifoFault(value)
        if kind != "sample": raise OSError(value)
        return value

    def close(self):
        try: self._stop()
        finally:
            if self.irq is not None: self.irq.close(); self.irq = None
