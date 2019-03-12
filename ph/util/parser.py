from ph import __version__
import ph.core.measurer
import ph.core.controller
import ph.core.coordinator
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter


def create_parser():
    p = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    p.add_argument(
        '--version', action='version', help='print version',
        version='%s' % __version__)
    p.add_argument(
        '-c', '--config', help='Path to config file', default='ph.ini')
    sub = p.add_subparsers(dest='command')
    ph.core.measurer.gen_parser(sub)
    ph.core.controller.gen_parser(sub)
    ph.core.coordinator.gen_parser(sub)
    return p
