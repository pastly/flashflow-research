#!/usr/bin/env bash
set -eux

D=$1
TOR_HOST=$2
TOR_HOST_CACHE_DIR=$3
BW_LIM=$4

pkill ph || true
pkill -9 tor || true
sleep 2

cd $D

rm -rfv datamanual?/
rsync -air $TOR_HOST:$TOR_HOST_CACHE_DIR/cached-* ./
for A in $(seq 1 1); do
    mkdir -pv datamanual${A}
    chmod 700 datamanual${A}
    cp -v cached-* datamanual${A}/
done
rm -fv cached-*

for A in $(seq 1 1); do
    nohup ./tor-securebw-bin -f torrc-manual-1 \
        --BandwidthRate $BW_LIM \
        --BandwidthBurst $BW_LIM \
        </dev/null \
		>measurer$A.stdout.txt \
		2>measurer$A.stderr.txt &
done

sleep 10
