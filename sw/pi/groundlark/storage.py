"""Owned recording sets, bounded retention and independently replayable segments."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
from threading import RLock
import time
import uuid
from functools import wraps

from .calibration import Calibrations
from .recording import Writer
from .session import Sessions

MiB = 1024 * 1024
SET_NAME = re.compile(r'[0-9]{20}-[a-f0-9]{32}\.(open|closed|interrupted)')


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.store.lock:
            return method(self, *args, **kwargs)
    return call


def sync_directory(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf8') as stream:
            json.dump(value, stream, allow_nan=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class Store:
    """Dedicated directory. Never delete unrelated files or follow symlinks.

    Capacity is checked against the backing device at provisioning; filesystem
    capacity here may be smaller because the OS lives on another partition.
    A single station process owns this object and its advisory process lock.
    """
    def __init__(self, root, *, reserve_bytes=2 * 1024**3, fraction=.8,
                 disk_usage=shutil.disk_usage, max_bytes=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if type(reserve_bytes) is not int or reserve_bytes < MiB or not .1 <= fraction <= .9:
            raise ValueError('storage reserve/fraction')
        self.reserve, self.fraction, self.disk_usage = reserve_bytes, fraction, disk_usage
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < MiB):
            raise ValueError('storage byte cap')
        self.max_bytes = max_bytes
        self.lock = RLock()
        self.active = set()
        self.deleted = 0
        self._closed_sizes = {}

    @contextmanager
    def exclusive(self):
        lock = (self.root / '.station.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                lock.write(b'0'); lock.flush(); lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            lock.close()

    def sets(self):
        result = []
        for path in self.root.iterdir():
            if not SET_NAME.fullmatch(path.name): continue
            if path.is_symlink() or not path.is_dir(): raise ValueError('unsafe recording set')
            if path.suffix != '.open' and path in self._closed_sizes:
                result.append((path,self._closed_sizes[path])); continue
            size = 0
            for child in path.iterdir():
                if child.is_symlink() or not child.is_file(): raise ValueError('unsafe recording member')
                size += child.stat().st_size
            result.append((path, size))
            if path.suffix != '.open': self._closed_sizes[path]=size
        return sorted(result, key=lambda pair: pair[0].name)

    def recover(self):
        """Keep interrupted bytes intact; expose their status without claiming completion."""
        with self.lock:
            for path, _ in self.sets():
                if path.suffix == '.open' and path not in self.active:
                    path.rename(path.with_suffix('.interrupted'))
            sync_directory(self.root)

    def status(self):
        with self.lock:
            usage = self.disk_usage(self.root)
            sets = self.sets()
            budget = max(0, min(int(usage.total * self.fraction), usage.total - self.reserve))
            if self.max_bytes is not None: budget = min(budget, self.max_bytes)
            return dict(total_bytes=usage.total, free_bytes=usage.free, budget_bytes=budget,
                        recording_bytes=sum(size for _, size in sets), reserve_bytes=self.reserve,
                        sets=len(sets), interrupted=sum(p.suffix == '.interrupted' for p, _ in sets),
                        deleted_sets=self.deleted)

    def make_room(self, incoming):
        with self.lock:
            state = self.status()
            used, free = state['recording_bytes'], state['free_bytes']
            for path, size in self.sets():
                if used + incoming <= state['budget_bytes'] and free - incoming >= self.reserve: break
                if path in self.active or path.suffix == '.open': continue
                # Every direct child was checked above; no recursive directory traversal.
                for child in path.iterdir(): child.unlink()
                path.rmdir()
                self._closed_sizes.pop(path,None)
                used -= size; free += size; self.deleted += 1
            if used + incoming > state['budget_bytes'] or free - incoming < self.reserve:
                raise OSError('recording reserve exhausted; active recordings preserved')

    def create(self):
        with self.lock:
            self.make_room(65536)
            path = self.root / f'{time.time_ns():020d}-{uuid.uuid4().hex}.open'
            path.mkdir()
            self.active.add(path)
            return path

    def listing(self):
        with self.lock:
            return [dict(name=p.name, bytes=size, state=p.suffix[1:]) for p, size in self.sets()]


class SegmentedWriter:
    def __init__(self, store, metadata, *, segment_bytes=8 * MiB, segment_seconds=300,
                 flush_seconds=2, observer=None):
        if not 65536 <= segment_bytes <= 64 * MiB or not 1 <= segment_seconds <= 3600:
            raise ValueError('segment bounds')
        if not .1 <= flush_seconds <= 30: raise ValueError('flush interval')
        self.store, self.metadata = store, dict(metadata)
        self.limit, self.duration = segment_bytes, int(segment_seconds * 1e9)
        self.flush_seconds, self.observer = flush_seconds, observer
        self.sessions = Sessions(Calibrations(metadata.get('calibrations', [])))
        self.writer = self.stream = self.path = None
        self.start = self.last = 0
        self.last_flush = time.monotonic()
        self.total_bytes = self.segments = 0
        self.checked_bytes = -65536

    def _open(self, at):
        self.path = self.store.create()
        metadata = dict(self.metadata, session_checkpoint=self.sessions.checkpoint())
        self.stream = (self.path / 'data.ssrec').open('xb')
        self.writer = Writer(self.stream, metadata, max_bytes=self.limit)
        self.start = self.last = at
        # Reannounce controls for existing tools and inventory displays. These
        # are idempotent, and preserve disconnect state by only emitting seen controls.
        from .messages import envelope
        for device, state in self.sessions.devices.items():
            if state.identity_seen:
                m = envelope(device, state.boot); m.identity.ParseFromString(state.identity)
                self.writer.message(m, at)
                if state.config_seen:
                    m = envelope(device, state.boot); m.configuration.ParseFromString(state.configuration)
                    self.writer.message(m, at)

    def _prepare(self, at):
        if self.writer is not None and (self.writer.written > self.limit - 8192 or at-self.start >= self.duration):
            self.close()
        if self.writer is None: self._open(at)
        if self.writer.written-self.checked_bytes >= 32768:
            self.flush(True)
            self.store.make_room(65536)
            self.checked_bytes = self.writer.written
        self.last = at

    @serialized
    def message(self, message, at):
        self._prepare(at)
        self.sessions.accept(message)
        self.writer.message(message, at)
        if self.observer: self.observer(message, at)
        self.flush()

    @serialized
    def event(self, code, detail, at, **fields):
        self._prepare(at)
        self.writer.event(code, detail, at, **fields)
        if code == 'usb_disconnected': self.sessions.disconnect(fields.get('device'))
        if self.observer: self.observer(dict(code=code, detail=detail, **fields), at)
        self.flush()

    def flush(self, force=False):
        if self.stream and (force or time.monotonic()-self.last_flush >= self.flush_seconds):
            self.stream.flush(); os.fsync(self.stream.fileno())
            self.last_flush = time.monotonic()

    @serialized
    def close(self, complete=True):
        if self.stream is None: return
        path = self.path
        try:
            if complete:
                self.writer.event('acquisition_summary', 'recording segment completed; acquisition may continue', self.last)
            self.flush(True)
            self.total_bytes += self.writer.written
        finally:
            self.stream.close()
            self.stream = self.writer = None
            self.store.active.discard(path)
        path.rename(path.with_suffix('.closed' if complete else '.interrupted'))
        sync_directory(self.store.root)
        self.segments += 1
        self.checked_bytes = -65536
