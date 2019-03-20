#!/usr/bin/env bash
set -eu

if (( "$#" != 2 ))
then
	echo "$0 <host> </path/to/sysctl.conf>"
	echo "$0 koios2 auto-run-scripts/sysctl.10M.txt"
	exit 1
fi

HOSTNAME=$1
FNAME=$2
DEFAULTS="$(dirname "$FNAME")/sysctl.defaults.txt"

if [ ! -f "$DEFAULTS" ]
then
	echo "$DEFAULTS does not exist. will not run without it, just in case"
	exit 1
fi

if [ ! -f "$FNAME" ]
then
	echo "$FNAME does not exist"
	exit 1
fi

ssh $HOSTNAME "
	sudo sysctl --load $FNAME
	sudo sysctl -w net.ipv4.route.flush=1
" || echo "Error applying sysctl settings from $FNAME"
