from ph import PKG_DIR
from configparser import (ConfigParser, ExtendedInterpolation)
from tempfile import NamedTemporaryFile
import logging
import logging.config
import os
import sys

log = logging.getLogger(__name__)


def _expand_path(p):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(p)))


def _read_config_file(conf, fname):
    assert os.path.isfile(fname)
    print('Reading config file %s' % fname, file=sys.stderr)
    log.debug('Reading config file %s', fname)
    with open(fname, 'rt') as fd:
        conf.read_file(fd, source=fname)
    return conf


def _get_default_config():
    conf = ConfigParser(
        interpolation=ExtendedInterpolation(),
        converters={'path': _expand_path})
    fname = os.path.join(PKG_DIR, 'config.default.ini')
    assert os.path.isfile(fname)
    return _read_config_file(conf, fname)


def _get_default_logging_config(conf=None):
    if not conf:
        conf = ConfigParser(
            interpolation=ExtendedInterpolation(),
            converters={'path': _expand_path})
    fname = os.path.join(PKG_DIR, 'config.log.default.ini')
    assert os.path.isfile(fname)
    return _read_config_file(conf, fname)


def get_config(args):
    conf = _get_default_config()
    conf = _get_default_logging_config(conf)
    if os.path.isfile(args.config):
        conf = _read_config_file(conf, args.config)
    return conf


def configure_logging(conf):
    with NamedTemporaryFile('w+t') as fd:
        conf.write(fd)
        fd.seek(0, 0)
        logging.config.fileConfig(fd.name)
