#!/bin/sh
# Inside an isolated Linux router namespace, place a client and server on
# different veth pairs. All probe packets must traverse the FORWARD hook.
set -eu
: "${MAGICNET_FIREWALL_FIXTURE:?use a disposable test namespace}"
root=$1
probe=$2
work=$(mktemp -d)
export MAGICNET_STATE_DIR="$work/state"
client=mna-client-$$
server=mna-server-$$
ctl() { sh "$root/cli" dns "$@"; }
cleanup() {
    ctl clear >/dev/null 2>&1 || :
    ip netns del "$client" || :
    ip netns del "$server" || :
    rm -rf "$work"
}
trap cleanup EXIT
for ns in "$client" "$server"; do ip netns add "$ns"; ip -n "$ns" link set lo up; done
i=1
for link in hotspot uplink; do
    if [ "$i" = 1 ]; then ns=$client; else ns=$server; fi
    ip link add "$link" type veth peer name peer
    ip link set peer netns "$ns"
    ip link set "$link" up
    ip -n "$ns" link set peer up
    ip addr add "192.0.$i.1/30" dev "$link"
    ip -n "$ns" addr add "192.0.$i.2/30" dev peer
    ip -6 addr add "2001:db8:$i::1/64" dev "$link" nodad
    ip -n "$ns" -6 addr add "2001:db8:$i::2/64" dev peer nodad
    ip -n "$ns" route add default via "192.0.$i.1"
    ip -n "$ns" -6 route add default via "2001:db8:$i::1"
    i=$((i+1))
done
echo 1 > /proc/sys/net/ipv4/ip_forward
echo 1 > /proc/sys/net/ipv6/conf/all/forwarding
export MNA_CLIENT_NS=/run/netns/$client MNA_SERVER_NS=/run/netns/$server
for action in allow drop clear; do
    expected=$action
    case $action in drop) ctl apply tether:hotspot;; clear) ctl clear; expected=allow;; esac
    for ipver in 4 6; do
        if [ "$ipver" = 4 ]; then MNA_TEST_ADDRESS=192.0.2.2; else MNA_TEST_ADDRESS=2001:db8:2::2; fi
        export MNA_TEST_ADDRESS
        for protocol in tcp udp; do
            "$probe" "$ipver" "$protocol" 53 10124 "$expected"
            "$probe" "$ipver" "$protocol" 853 10124 "$expected"
            "$probe" "$ipver" "$protocol" 1053 10124 allow
        done
    done
done
echo MNA_TETHER_FORWARD_OK
