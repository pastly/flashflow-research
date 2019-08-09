from ..lib.chunkpayloads import PingMeasureResult, BwMeasureResult
from statistics import median
import logging

log = logging.getLogger(__name__)


def total_bw_bytes(results, include_trusted=True, include_untrusted=True):
    '''
    Count the number of bytes transferred in all the results, and return the
    sum.
    '''
    agg = 0
    for m in results:
        for r in [_ for _ in results[m] if isinstance(_, BwMeasureResult)]:
            if r.is_trusted and include_trusted:
                agg += r.amount
            elif not r.is_trusted and include_untrusted:
                agg += r.amount
    return agg


def report_interval_needed(results, min_interval=1):
    '''
    Given a dictionary containing ping results (keys: something representing
    measurers, values: lists of PingMeasureResult [and possibly others]),
    calculate how often measurers should report bandwidth results back to the
    coordinator.

    If there is no RTT data in the results, returns min_interval

    Additional arguments:
        min_interval: the minimum value this function can return, in seconds
    '''
    max_rtt = max_rtt_in_results(results)
    if max_rtt is None:
        return min_interval
    return max(min_interval, max_rtt * 3)


def max_rtt_in_results(results):
    '''
    Given a dictionary of results (keys: something representing measurers,
    values: a list of results that include PingMeasureResults and maybe
    other types [ignored]), return the max median RTT.

    If there is no RTT data in the results, this will return None
    '''
    max_rtt = -1
    for m in results:
        rtts = [r.rtt for r in results[m] if isinstance(r, PingMeasureResult)]
        if not len(rtts):
            continue
        max_rtt = max(median(rtts), max_rtt)
    if max_rtt < 0:
        return None
    return max_rtt


def get_ping_results(results):
    '''
    Filter out and return just the PingMeasureResult values in the result
    dictionary
    '''
    ret = {}
    for m in results:
        ret[m] = [r for r in results[m] if isinstance(r, PingMeasureResult)]
    return ret


def get_bw_results(results):
    '''
    Filter out and return just the BwMeasureResult values in the result
    dictionary
    '''
    ret = {}
    for m in results:
        ret[m] = [r for r in results[m] if isinstance(r, BwMeasureResult)]
    return ret


def num_covered_report_intervals(results, min_report_interval=1):
    '''
    Determine the minimum number of report intervals covered by each measurer's
    results.

    Additional arguments:
        min_report_interval: as in report_interval_needed()
    '''
    report_interval = report_interval_needed(results, min_report_interval)
    min_report_intervals = None
    bw_results = get_bw_results(results)
    for m in bw_results:
        if not len(bw_results[m]):
            return 0
        start = bw_results[m][0].start
        end = bw_results[m][-1].end
        if end <= start:
            log.warn(
                'Earliest end time %d is before latest start time %d. Saying '
                'there are no report intervals', end, start)
            return 0
        if min_report_intervals is None:
            min_report_intervals = (end - start)/report_interval
        else:
            min_report_intervals = min(
                (end - start)/report_interval,
                min_report_intervals)
    min_report_intervals = int(min_report_intervals)
    return min_report_intervals if min_report_intervals > 0 else 0


def _one_measurer_bandwidth_during_window(
        measurer_bw_results, start_time, end_time, use_medians):
    '''
    '''
    window_size = end_time - start_time
    kept_results = []
    for r in measurer_bw_results:
        if (r.start < end_time and r.end > start_time) or \
                (r.end > start_time and r.start < end_time):
            kept_results.append(r)
    earliest_start = kept_results[0].start
    latest_end = kept_results[-1].end
    actual_duration = latest_end - earliest_start
    if not use_medians:
        transferred_bytes = sum([r.amount for r in kept_results])
        adjusted_bytes = transferred_bytes * window_size / actual_duration
        res = BwMeasureResult(start_time, end_time, adjusted_bytes, None)
        log.debug(
            'Calculated measurer bw of %f Mbps over %d/%d of its reported '
            'results. This represents %f seconds (t=%f-%fs), and the target '
            'window_size is %f seconds (t=%f-%fs).',
            res.bandwidth_bits(units='M'),
            len(kept_results), len(measurer_bw_results), actual_duration,
            earliest_start-measurer_bw_results[0].start,
            latest_end-measurer_bw_results[0].start,
            window_size,
            start_time-measurer_bw_results[0].start,
            end_time-measurer_bw_results[0].start)
        return res
    else:
        med_bw = median([res.bandwidth() for res in kept_results])
        num_bytes = window_size * med_bw
        res = BwMeasureResult(start_time, end_time, num_bytes, None)
        return res


def all_measurer_bandwidth_during_window(
        bw_results, start_time, end_time, use_medians):
    indiv_results = []
    for m in bw_results:
        indiv_results.append(_one_measurer_bandwidth_during_window(
            bw_results[m], start_time, end_time, use_medians))
    amount = sum([r.amount for r in indiv_results])
    if amount == 0:
        # small but non-zero amount to avoid divide-by-zero errors elsewhere
        amount = 0.0000001
    res = BwMeasureResult(start_time, end_time, amount, None)
    log.debug(
        'Calculated total bandwidth of %f Mbps over %f seconds',
        res.bandwidth_bits(units='M'), res.duration)
    return res


def results_are_steady(
        results, allowed_change=0.01, window_decay_factor=0.5,
        steady_report_intervals=5,
        min_report_interval=1, use_medians=False):
    '''
    Given a dictionary of results (keys: someething representing measurers,
    values: a list of Ping- and BwMeasureResults), determine if the bandwidth
    results seem to have reached steady state, thus could be halted.

    If the results seem to indicate steady state, return True and the estimated
    setady state bandwidth as a BwMeasureResult. Otherwise return (False, None)

    Additional arguments:
        allowed_change: maximum amount a result can change in relationship to
            the previous result and still be considered steady state.
            0.10 == 10%
        window_decay_factor: factor controlling how closely the start of the
            measurement duration window follows the end.
            0.999 means almost none of the results (start always near end),
            0 means all of the results
            0.5 means keep half the results
        steady_report_intervals: once results are steady for this many report
            intervals we are allowed to return True
        min_report_interval: as in report_interval_needed()

    More about window_decay_factor:
        Here is a diagram showing how various values affect from what points in
        time measurement results are considered. We have 10 seconds of results
        so far, and this shows what fraction of the results we will use in the
        calculation of the target's bandwidth over this 10s period.

        t=0 .................................... t=10
        |----------------------------------------| 10 seconds
        |                              |---------| factor = 0.75
        |                    |-------------------| factor = 0.50
        |          |-----------------------------| factor = 0.25

        See how with a factor of 0.50 we always consider the newest half of
        bandwidth result data. With t=10s we consider the newest 5s of data,
        with t=60s we'd consider the newest 30s of data.

    More about determining steady state:
        First we calculate the average bandwidth over a handful of windows.
        For example, if steady_report_intervals is 3 ...

        t=0 .............................................. t=10
        |--------------------------------------------------| 10 seconds
        |          |-----------------------|               | win 1
        |            |-----------------------------|       | win 2
        |              |-----------------------------------| win 3

        Notice:
            - Windows grow in size as time passes (they include new data at the
            end faster than they ignore old data at the beginning)

        For each of the above windows we calculate the average bandwidth
        receved during it. Once there is less than **allowed_change** change
        between each window, we determine that we've reached steady state.

    '''
    assert window_decay_factor >= 0
    assert window_decay_factor < 1
    assert allowed_change >= 0
    assert allowed_change <= 1
    assert steady_report_intervals >= 2
    num_report_intervals = num_covered_report_intervals(results)

    if num_report_intervals < steady_report_intervals:
        log.debug(
            'Not steady: not enough data yet. Only %d of %d report intervals '
            'so far.', num_report_intervals, steady_report_intervals)
        return False, None

    bw_results = get_bw_results(results)
    start_time = max([bw_results[m][0].start for m in bw_results])
    end_time = min([bw_results[m][-1].end for m in bw_results])
    max_duration = end_time - start_time

    # Here we calculate the various windows needed for each call to
    # all_measurer_bandwidth_during_duration(). We put the oldest window first,
    # which will have the largest gap between its end and the end of the data.
    report_interval = report_interval_needed(results, min_report_interval)
    arg_sets = []
    for i in range(steady_report_intervals-1, 0-1, -1):
        gap_at_end = i * report_interval
        window_size = (max_duration - gap_at_end) * (1 - window_decay_factor)
        this_end_time = end_time - gap_at_end
        this_start_time = this_end_time - window_size
        arg_sets.append((
            bw_results, this_start_time, this_end_time, use_medians))

    aggregate_bandwidths = []
    for args in arg_sets:
        aggregate_bandwidths.append(
            all_measurer_bandwidth_during_window(*args))

    last_idx = 0
    for res in aggregate_bandwidths:
        log.debug('%f bytes', res.amount)
    for i in range(last_idx+1, len(aggregate_bandwidths)):
        last_bw = aggregate_bandwidths[last_idx].bandwidth_bits(units='M')
        new_bw = aggregate_bandwidths[i].bandwidth_bits(units='M')
        change_fract = 1 - (new_bw / last_bw)
        if change_fract > allowed_change or change_fract < -1 * allowed_change:
            log.debug(
                '%f Mbps to %f Mbps is too big a change (%f%%). '
                'Not steady yet',
                last_bw, new_bw, change_fract * 100)
            return False, None
        else:
            log.debug(
                '%f Mbps to %f Mbps is fine (%f%%) ...',
                last_bw, new_bw, change_fract * 100)
        last_idx = i
    res = aggregate_bandwidths[-1]
    log.debug(
        'Results considered steady. Returning %f Mbps over %fs (t=%f-%fs)',
        res.bandwidth_bits(units='M'), res.duration,
        res.start - start_time,
        res.end - start_time
    )
    return True, res


def trickle_results(results):
    '''
    Used in plotting/stats stuff, not during data collection.

    Given a full dictionary of results, strip it down to just the ping results,
    then slowly add more bandwidth measurement results as we keep yielding it.
    This is used to simulate a coordinator slowly getting more data from the
    measurers over time so that we can see if/when the coordinator would first
    consider the measurement steady and tell everyone to stop.
    '''
    bw_results = get_bw_results(results)
    collapsed_results = [(m, res) for m in bw_results for res in bw_results[m]]
    collapsed_results = sorted(collapsed_results, key=lambda item: item[1].end)
    return_results = get_ping_results(results)
    for measurer, res in collapsed_results:
        if measurer not in return_results:
            return_results[measurer] = []
        log.debug('Adding result: %fMbps over %fs ending at %f',
                  res.bandwidth_bits(units='M'), res.duration, res.end)
        return_results[measurer].append(res)
        yield return_results
