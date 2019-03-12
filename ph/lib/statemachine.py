import logging

log = logging.getLogger(__name__)


class InvalidTransition(Exception):
    def __init__(self, from_state, to_state):
        self._from = from_state
        self._to = to_state

    def __str__(self):
        return "InvalidTransition: Cannot transition from %s to %s" %\
            (self._from, self._to)


class StateMachine:
    '''
    **state_transition_map** should be a dict detailing what state transitions
    are allowed. Keys are source states and values are a set of allowed
    destination states.

    {
        'blue': set('orange'),
        'orange': set('green', 'red', 'orange'),
        'red': set('green')
        'green': set('blue')
    }

    if **allow_noop**, allow transitions from state 'foo' to itself. This is a
    convenience option, as you could allow this in the **state_transition_map**
    manually.
    '''
    def __init__(self, state_transition_map, initial, allow_noop=False):
        self._current = initial
        self._map = state_transition_map
        if allow_noop:
            for src in self._map:
                self._map[src].add(src)

    @property
    def current(self):
        return self._current

    def transition(self, dest):
        if self.allowed_transition(dest):
            log.info('Transitioning from %s to %s', self._current, dest)
            self._current = dest
        else:
            raise InvalidTransition(self._current, dest)

    def allowed_transition(self, dest):
        src = self._current
        state_map = self._map
        if src not in state_map:
            log.debug(
                'Disallowing transition because %s is not a source node in '
                'map', src)
            return False
        allowed_dests = state_map[src]
        if dest not in allowed_dests:
            log.debug(
                'Disallowing transition because %s is not a destination node '
                'from source %s in map', dest, src)
            return False
        return True

    def __eq__(self, rh):
        return self.current == rh
