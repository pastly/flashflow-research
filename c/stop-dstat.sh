#!/usr/bin/env bash
set -eux
(ps aux | grep -v grep | grep dstat | grep python) || true
(ps aux | grep -v grep | grep dstat | grep python | awk '{print $2}' | xargs kill ) || true;
#pkill python || true;
#pkill dstat || true;
