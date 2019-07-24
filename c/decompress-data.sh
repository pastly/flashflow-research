#!/usr/bin/env bash
set -eux

D=$1

find $D -type f -name '*.xz' | xargs xz -dvf
