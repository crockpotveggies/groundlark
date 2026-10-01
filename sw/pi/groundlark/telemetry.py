"""Bounded local telemetry. Raw-count RSAM has no implied velocity calibration."""
from collections import deque


class Summaries:
    def __init__(self, window_seconds=60):
        if type(window_seconds) is not int or not 1 <= window_seconds <= 3600:
            raise ValueError('summary window')
        self.window = window_seconds * 1_000_000_000
        self.current = None
        self.results = deque(maxlen=120)

    def _finish(self):
        if self.current is None: return
        c = self.current
        self.results.append(dict(device=c['device'], boot=str(c['boot']), sensor=9,
            configuration_revision=c['revision'], period_ns=str(c['period']),
            start_ns=str(c['start']), end_ns=str(c['start']+self.window), clock_domain=c['domain'],
            samples=c['count'], missing=c['missing'], loss_unknown=c['unknown'],
            mean_absolute_counts=c['sum']/c['count'] if c['count'] else None,
            complete=not c['unknown'] and not c['missing'] and c['count'] >= c['expected']
                and c['first']<=c['start']+c['period'] and c['last']>=c['start']+self.window-c['period'],
            expected_samples=c['expected'], method='mean(abs(raw ADC counts)); no filter or DC removal',
            calibration=None, utc=None))

    def observe(self, m, period_ns):
        if m.WhichOneof('body') != 'batch' or m.batch.sensor_id != 9: return
        for index,s in enumerate(m.batch.samples):
            start = s.time.acquisition_ns // self.window * self.window
            identity = (m.device_id, m.boot_id, start, s.time.domain,m.batch.configuration_revision,period_ns)
            if self.current is None or self.current['key'] != identity:
                self._finish()
                self.current = dict(key=identity, device=m.device_id, boot=m.boot_id, start=start,
                    domain=s.time.domain, revision=m.batch.configuration_revision,
                    count=0, missing=0, unknown=False, sum=0,
                    expected=self.window//period_ns, sequence=None, period=period_ns,
                    first=s.time.acquisition_ns,last=s.time.acquisition_ns)
            c = self.current
            c['unknown'] |= not m.batch.HasField('dropped_before')
            if c['sequence'] is not None: c['missing'] += max(0, s.sequence-c['sequence']-1)
            elif index==0 and m.batch.HasField('dropped_before'):c['missing']+=m.batch.dropped_before
            c['last']=s.time.acquisition_ns
            c['sequence'] = s.sequence
            if s.quality == 1 and s.HasField('geophone'):
                c['count'] += 1; c['sum'] += abs(s.geophone.counts)
            else: c['missing'] += 1

    def interrupt(self):
        if self.current:
            self.current['unknown'] = True
            self._finish()
            self.current = None
