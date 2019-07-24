#!/usr/bin/env bash
set -eux

D=$1
FNAME=$2
FP=$3
shift; shift; shift

DURATION=30
PASSWORD=password

cd $D/c
rm -fv $FNAME ${FNAME}.xz

date
./flashflow <(echo $FP) $DURATION $PASSWORD $@ > $FNAME
date
