#!/usr/bin/env bash
set -eu

if (( "$#" != 1 ))
then
	echo "$0 </path/to/sysctl.conf>"
	echo "$0 he/sysctl.32M.txt"
	exit 1
fi

FNAME=$1
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

sudo sysctl -p $FNAME
sudo sysctl -w net.ipv4.route.flush=1
