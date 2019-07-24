#!/usr/bin/env bash
set -eux

D=$1
TOR_HOST=$2
TOR_HOST_CACHE_DIR=$3
BW_LIM=$4
N=$5

pkill ph || true
pkill -9 tor || true
sleep 2

cd $D

rm -rfv flashflow-tordata-*/
rsync -air $TOR_HOST:$TOR_HOST_CACHE_DIR/cached-* ./
for A in $(seq 1 $N); do
    mkdir -pv flashflow-tordata-${A}
    chmod 700 flashflow-tordata-${A}
    cp -v cached-* flashflow-tordata-${A}/
done
rm -fv cached-*

for A in $(seq 1 $N); do
    nohup ./tor-securebw-bin -f c/flashflow-torrc-$A \
        --BandwidthRate $BW_LIM \
        --BandwidthBurst $BW_LIM \
        </dev/null \
		>measurer$A.stdout.txt \
		2>measurer$A.stderr.txt &
done

sleep 10
