#!/usr/bin/env bash
set -eux

D=$1
FNAME=$2
FP=$3
shift; shift; shift

DURATION=30
PASSWORD=password

cd $D/c
rm -fv $FNAME

date
./flashflow <(echo $FP) $DURATION $PASSWORD $@ | xz -T 2 > $FNAME
date
