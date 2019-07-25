#!/usr/bin/env bash
set -eux

D=$1
FNAME=$2
FP=$3
DURATION=$4
PASSWORD=$5
shift; shift; shift; shift; shift


cd $D/c
rm -fv $FNAME

date
./flashflow <(echo $FP) $DURATION $PASSWORD $@ | xz -T 2 > $FNAME
date
