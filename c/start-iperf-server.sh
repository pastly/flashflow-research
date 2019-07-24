#!/usr/bin/env bash
set -eux

BIN=$1
IP=$2
PORT=$3

CMD=("$BIN" "--server" "$IP" "--daemon" "--port" "$PORT" "--json")

${CMD[@]}
