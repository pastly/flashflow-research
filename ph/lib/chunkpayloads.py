import logging

log = logging.getLogger(__name__)


class Identify:
    def __init__(self, msg):
        assert isinstance(msg, str)
        self._msg = msg

    @property
    def message(self):
        return self._msg


class ConnectToTargetCommand:
    def __init__(self, target, success=None):
        assert isinstance(target, str)
        assert len(target) == 40
        assert success is None or isinstance(success, bool)
        self._target = target
        self._success = success

    @property
    def target(self):
        return self._target

    @property
    def success(self):
        return self._success


class Aborted:
    def __init__(self, msg=None):
        self._msg = msg

    @property
    def msg(self):
        return self._msg

class MeasureCommand:
    def __init__(self, target, repeat, num_measurers=None,
                 num_conns_per_measurer=None):
        assert isinstance(target, str)
        assert len(target) == 40
        assert isinstance(repeat, int)
        self._target = target
        self._repeat = repeat
        self._num_measurers = num_measurers
        self._num_conns_per_measurer = num_conns_per_measurer

    @property
    def target(self):
        return self._target

    @property
    def repeat(self):
        return self._repeat

    @property
    def num_measurers(self):
        return self._num_measurers

    @property
    def num_conns_per_measurer(self):
        return self._num_conns_per_measurer


class MeasureCommandStop(MeasureCommand):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)


class MeasureCommandPing(MeasureCommand):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)


class MeasureCommandBw(MeasureCommand):
    def __init__(self, pause_start, duration, pause, *a, **kw):
        '''
        **pause_start**: time to wait before starting first measurement
        **duration**: time each measurement should last
        **pause**: time to wait between measurements
        '''
        super().__init__(*a, **kw)
        self._pause_start = pause_start
        self.duration = duration
        self._pause = pause
        self.report_interval = None

    @property
    def pause_start(self):
        return self._pause_start

    @property
    def pause(self):
        return self._pause

    def adjust_pause_start(self, amount):
        log.debug(
            'Adjusting pause_start: old=%f change=%f new=%f', self.pause_start,
            amount, self.pause_start+amount)
        self._pause_start += amount


class MeasureResult:
    pass


class PingMeasureResult(MeasureResult):
    def __init__(self, send_time, recv_time):
        self._send = send_time
        self._recv = recv_time

    @property
    def send_time(self):
        return self._send

    @property
    def recv_time(self):
        return self._recv

    @property
    def rtt(self):
        return self.recv_time - self.send_time

    @property
    def latency(self):
        return self.rtt / 2.0


class BwMeasureResult(MeasureResult):
    def __init__(self, start_time, end_time, bytes_transferred, is_trusted):
        self._start = start_time
        self._end = end_time
        self._amount = bytes_transferred
        self._is_trusted = is_trusted

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    @property
    def duration(self):
        return self.end - self.start

    @property
    def amount(self):
        return self._amount

    @property
    def is_trusted(self):
        return self._is_trusted

    def bandwidth(self, units=None):
        '''
        units can be 'K' or 'M' for KBps and MBps
        '''
        rate = (self.amount * 1.0) / self.duration
        if units is None:
            return rate
        elif units == 'K':
            return rate / 1000.0
        elif units == 'M':
            return rate / 1000.0 / 1000.0

    def bandwidth_bits(self, units=None):
        '''
        units can be 'K' or 'M' for Kbps and Mbps
        '''
        return self.bandwidth(units) * 8.0
