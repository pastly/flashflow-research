from ..util.rand import randbytes

class NearlyRandBytes:
    def __init__(self, num_predictable, predictable_byte=b'K'):
        self._buf = predictable_byte * num_predictable
        self._max_predictable = len(self._buf)
        self._num_sent_predictable = 0

    def _next_rand_byte(self):
        return randbytes(1)

    def get(self, n):
        '''
        Returns two byte strings.
        - The first is a byte string of **n** nearly random bytes
        - The second is a byte string of just the actually random bytes that
        are sprinkled into the first string

        Assuming **num_predictable** is 5, the byte to use for predictable
        bytes is 'K', and denoting random bytes with 'r', this function will
        return:
            KKKKKrKKKKKrKKKKKr ...
        Every 6th byte we return is random in this set up.

        A NearlyRandBytes object will remember what it has returned previously
        such that every 6th byte *across .get() calls* is random.
        - Ask for 3: get KKK
        - Ask for 5: get KKrKK
        - Ask for 5: get KKKrK
        - Ask for 6: get KKKKrK
        '''
        ret_str = b''  # The full nearly random string of length **n**
        ret_rand = b''  # Only the actually random bytes in **ret_str**
        still_need = n
        while still_need > 0:
            # How many not-random bytes can we still return before we have to
            # send a random byte?
            predictable_space_left = self._max_predictable - \
                self._num_sent_predictable
            # If the number of bytes that we still need is not greater than the
            # remaining number of not-random bytes we can return, then we can
            # simply pad out **ret_str** with predictable bytes
            if still_need <= predictable_space_left:
                ret_str += self._buf[:still_need]
                self._num_sent_predictable += still_need
                still_need = 0
            # Otherwise (if the number of bytes that we still need is greater
            # than the remaining number of not-random bytes we can return), we
            # have to
            # - Pad out **ret_str** with as many not-random bytes as we can
            # - Get a random byte
            # - Put the random byte in **ret_str** and **ret_rand**
            # - Allow ourselves to resume returning not-random bytes
            else:
                ret_str += self._buf[:predictable_space_left]
                still_need -= predictable_space_left
                rand_byte = self._next_rand_byte()
                ret_str += rand_byte
                ret_rand += rand_byte
                still_need -= 1
                self._num_sent_predictable = 0
        assert still_need == 0
        assert len(ret_str) == n
        return ret_str, ret_rand
