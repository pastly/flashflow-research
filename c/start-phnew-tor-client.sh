#!/usr/bin/env bash
set -eux

D=$1
TOR_HOST=$2
TOR_HOST_CACHE_DIR=$3
BW_LIM=$4
N=$5
BG_CLIENT_N=$6

pkill ph || true
pkill -9 tor || true
sleep 2

cd $D

# rm -rfv flashflow-tordata-*/
# rsync -air $TOR_HOST:$TOR_HOST_CACHE_DIR/cached-* ./
# for A in $(seq 1 $N); do
#     mkdir -pv flashflow-tordata-${A}
#     chmod 700 flashflow-tordata-${A}
#     cp -v cached-* flashflow-tordata-${A}/
# done
# if (( "$BG_CLIENT_N" > "0" )); then
#     mkdir -pv flashflow-tordata-${BG_CLIENT_N}
#     chmod 700 flashflow-tordata-${BG_CLIENT_N}
#     cp -v cached-* flashflow-tordata-${BG_CLIENT_N}/
# fi
# rm -fv cached-*

for A in $(seq 1 $N); do
    nohup ./tor-securebw-bin -f c/flashflow-torrc-$A \
        --BandwidthRate $BW_LIM \
        --BandwidthBurst $BW_LIM \
        </dev/null \
		>measurer$A.stdout.txt \
		2>measurer$A.stderr.txt &
done
if (( "$BG_CLIENT_N" > "0" )); then
    nohup ./tor-securebw-bin -f c/flashflow-torrc-$BG_CLIENT_N \
        --BandwidthRate 125000 \
        --BandwidthBurst 125000 \
        </dev/null \
		>measurer$BG_CLIENT_N.stdout.txt \
		2>measurer$BG_CLIENT_N.stderr.txt &
fi

sleep 10
