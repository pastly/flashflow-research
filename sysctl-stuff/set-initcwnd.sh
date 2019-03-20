#!/usr/bin/env bash
set -eu
# Before ever doing any changes, the default route was:
# he:
#     default via 216.218.222.9 dev eno1 proto static metric 100
# ddns:
#     default via 192.168.1.1 dev enp0s25 proto dhcp metric 100
# amjohn:
#     default via 23.91.124.1 dev eth0

if (( "$#" != 1 ))
then
	echo "$0 <initcwnd>"
	echo "$0 10"
	exit 1
fi

initcwnd=$1
shift

defroute="$(ip route | grep '^default' | head -n 1)"
echo BEFORE: $defroute
sudo ip route change $defroute initcwnd $initcwnd
defroute="$(ip route | grep '^default' | head -n 1)"
echo "AFTER:  $defroute"
