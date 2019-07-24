#!/usr/bin/env bash
set -eux

D=$1
FNAME=$2
FP=$3
shift; shift; shift

SOCKS_PER_TOR=$((160/$(($#/2))))
DURATION=30
PASSWORD=password

cd $D/c
rm -fv $FNAME ${FNAME}.xz

date
./flashflow <(echo $FP) $SOCKS_PER_TOR $DURATION $PASSWORD $@ | tee $FNAME
date
