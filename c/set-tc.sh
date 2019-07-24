#!/usr/bin/env bash
set -eux

DEV=$1
RATE=$2
LAT=$3

if [[ "$(hostname)" != *"arvixecloud"* ]]; then
    CMD=("sudo" "tc" "qdisc" "add" "dev" "$DEV" "root" "netem")
    if [[ "$RATE" != "unlim" ]]; then
        CMD+=("rate" "$RATE")
    fi
    if (( "$LAT" != "0" )); then
        CMD+=("latency" "${LAT}ms")
    fi
    ${CMD[@]}
else
    # This should work on a basic level (to the extend we even have confidence
    # in tc/netem) but the burst/limit values basically came out of my ass.
    CMD_RATE="sudo tc qdisc add dev $DEV root handle 1:0 tbf rate $RATE burst 100k limit 100k"
    CMD_LAT="sudo tc qdisc add dev $DEV parent 1:1 handle 10: netem delay ${LAT}ms"
    $CMD_RATE
    $CMD_LAT

fi
sudo tc -p qdisc ls dev $DEV
