#!/usr/bin/env bash
set -eux

(ps aux | grep -v grep | grep python | grep bw-events | awk '{print $2}' | xargs kill) || true
