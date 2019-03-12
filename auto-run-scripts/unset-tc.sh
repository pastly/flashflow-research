#!/usr/bin/env bash
set -eu

HOSTNAME=$1
DEV=$2

echo "Unsetting tc"
ssh $HOSTNAME "
	sudo tc qdisc del dev $DEV root
	"
