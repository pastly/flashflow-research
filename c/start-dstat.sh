#!/usr/bin/env bash
set -eux

OUT_FNAME=$1

(ps aux | grep -v grep | grep dstat | grep python) || true
(ps aux | grep -v grep | grep dstat | grep python | awk '{print $2}' | xargs kill ) || true
#pkill python || true;
#pkill dstat || true;
rm -fv $OUT_FNAME

nohup dstat --output $OUT_FNAME &>/dev/null &

sleep 2
