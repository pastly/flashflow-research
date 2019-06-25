from ph.lib.chunkpayloads import MeasureCommandBw


def get_help_string():
    s = 'Known commands are: %s' % ' '.join(sorted(KNOWN_COMMANDS.keys()))
    return s


class MalformedControllerCommand(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return 'Malformed command. "%s"' % self._msg


class UnknownControllerCommand(Exception):
    def __init__(self, command):
        self._command = command

    def __str__(self):
        return 'Uknown command: "%s"' % self._command


class ControllerCommand:
    def __init__(self, command_str):
        self._str = command_str

    def __str__(self):
        return self._str

    @property
    def is_local(self):
        if hasattr(self, '_is_local'):
            return self._is_local
        raise NotImplementedError()

    @staticmethod
    def from_string(command_str):
        words = command_str.split(' ')
        first = words[0].lower()
        if first not in KNOWN_COMMANDS:
            raise UnknownControllerCommand(first)
        return KNOWN_COMMANDS[first]['class'](command_str)


class ControllerCommandHelp(ControllerCommand):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._is_local = True


class ControllerCommandMeasure(ControllerCommand):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._is_local = False
        assert self._str.startswith('measure')
        args = self._str.split(' ')[1:]
        if len(args) != 4:
            raise MalformedControllerCommand(self.get_help_string())
        self._name = args[0]
        target_fp = args[1]
        num_measurers = int(args[2])
        num_conns_overall = int(args[3])
        repeat = 1
        pause_start = 0.100
        duration = None
        pause = 0.000
        self._measure_commands = [
            MeasureCommandBw(
                pause_start, duration, pause, target_fp, repeat,
                num_measurers, num_conns_overall)]

    @property
    def measure_commands(self):
        return self._measure_commands

    @property
    def name(self):
        return self._name

    def get_help_string(self):
        return 'measure <filename> <target_fp> <num_measurers> '\
            '<num_conns_overall>'


class ControllerCommandQuit(ControllerCommand):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._is_local = True


class ControllerCommandStatus(ControllerCommand):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._is_local = False


KNOWN_COMMANDS = {
    'help': {
        'class': ControllerCommandHelp,
    },
    'measure': {
        'class': ControllerCommandMeasure,
    },
    'quit': {
        'class': ControllerCommandQuit,
    },
    'status': {
        'class': ControllerCommandStatus,
    }
}
