#!/usr/bin/env python3
from ph import __version__, __software_name__
import ph.core.measurer
import ph.core.controller
import ph.core.coordinator
from .util.parser import create_parser
from .util.config import get_config, configure_logging
from nacl import __version__ as nacl_version
import asyncio
import logging
import platform
import cProfile

log = logging.getLogger(__name__)


def _get_startup_line():
    py_ver = platform.python_version()
    py_plat = platform.platform()
    return '%s %s running with python %s on %s and libraries nacl %s' % \
        (__software_name__, __version__, py_ver, py_plat, nacl_version)


def main():
    parser = create_parser()
    args = parser.parse_args()
    if not args.config:
        parser.print_help()
        exit(1)
    conf = get_config(args)
    configure_logging(conf)
    def_args = [args, conf]
    def_kwargs = {}
    commands = {
        'measurer': {'f': ph.core.measurer.main,
                     'a': def_args, 'kw': def_kwargs},
        'controller': {'f': ph.core.controller.main,
                       'a': def_args, 'kw': def_kwargs},
        'coordinator': {'f': ph.core.coordinator.main,
                        'a': def_args, 'kw': def_kwargs},
    }
    if args.command not in commands:
        parser.print_help()
        exit(1)
    log.info(_get_startup_line())
    comm = commands[args.command]
    loop = asyncio.get_event_loop()
    # pr = cProfile.Profile()
    # pr.enable()
    try:
        loop.run_until_complete(comm['f'](*comm['a'], **comm['kw']))
    except KeyboardInterrupt:
        # print('')
        pass
    # finally:
    #     pr.disable()
    #     pr.print_stats('cumulative')
