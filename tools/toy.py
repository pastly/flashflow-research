#!/usr/bin/env python3
from ph.lib.chunkpayloads import PingMeasureResult, BwMeasureResult
import pickle
import sys

for fname in sys.argv[1:]:
    dat = None
    with open(fname, 'rb') as fd:
        dat = pickle.load(fd)

    command = dat['command']
    results = dat['results']

    print('----', fname, '----')
    print(type(command).__name__, command)
    for res in results:
        if isinstance(res, PingMeasureResult):
            print('Ping (ms) %f' % (float(res.rtt)*1000.0))
        elif isinstance(res, BwMeasureResult):
            print('BW (Mbps) %f' % res.bandwidth_bits(units='M'))
            print('    over %f seconds' % res.duration)
        elif isinstance(res, int):
            measurer_hash = res
            print('From measurer %d:' % measurer_hash)
            for res in results[measurer_hash]:
                if isinstance(res, PingMeasureResult):
                    print('    Ping (ms) %f' % (float(res.rtt)*1000.0))
                elif isinstance(res, BwMeasureResult):
                    print('    BW (Mbps) %f %s' %
                        (res.bandwidth_bits(units='M'),
                        'trusted' if res.is_trusted else 'untrusted'))
                    print('        over %f seconds (%0.2f - %0.2f)' % (
                        res.duration, res.start, res.end))
        else:
            print('Can\'t print info on', type(res).__name__)
