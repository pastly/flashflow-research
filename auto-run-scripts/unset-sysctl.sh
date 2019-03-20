#!/usr/bin/env bash
set -eu

if (( "$#" != 2 ))
then
	echo "$0 <host> </path/to/sysctl.conf>"
	echo "$0 koios2 auto-run-scripts/sysctl.defaults.txt"
	exit 1
fi

HOSTNAME=$1
FNAME=$2

if [ ! -f "$FNAME" ]
then
	echo "$FNAME does not exist"
	exit 1
fi

ssh $HOSTNAME "
	sudo sysctl -p $FNAME
" || echo "Error applying sysctl settings from $FNAME"
