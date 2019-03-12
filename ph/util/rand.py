import os
import random

_sys_random = random.SystemRandom()


def randbytes(n):
    return os.urandom(n)
