#!/usr/bin/env bash
set -eux

DEV=$1

sudo tc qdisc del dev $DEV root
