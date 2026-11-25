#!/bin/sh
# Inside a dedicated root network namespace or disposable Linux guest only.
set -eu
: "${MAGICNET_FIREWALL_FIXTURE:?use a disposable test namespace}"
root=$1
probe=$2
work=$(mktemp -d)
export MAGICNET_STATE_DIR="$work/state"
ctl() { sh "$root/cli" dns "$@"; }
cleanup() { ctl clear >/dev/null 2>&1 || :; rm -rf "$work"; }
trap cleanup EXIT
ctl apply uid:10123
for ip in 4 6; do
    for proto in udp tcp; do
        for port in 53 853; do
            "$probe" "$ip" "$proto" "$port" 10123 drop
            "$probe" "$ip" "$proto" "$port" 10124 allow
        done
        "$probe" "$ip" "$proto" 1053 10123 allow
    done
done
# Simulate a tether interface with loopback. INPUT covers traffic destined
# for a DNS listener on the host. FORWARD is inspected in the Android matrix.
ctl apply tether:lo
for ip in 4 6; do
    "$probe" "$ip" udp 53 10124 drop
    "$probe" "$ip" tcp 853 10124 drop
done
# Force the second family's transaction to fail and verify the first family's
# actual packet disposition still matches its previous policy.
mkdir "$work/fail"
printf '#!/bin/sh\nexit 42\n' > "$work/fail/ip6tables-restore"
chmod 755 "$work/fail/ip6tables-restore"
if PATH="$work/fail:$PATH" ctl apply uid:10123; then exit 1; fi
"$probe" 4 udp 53 10124 drop
ctl clear
for ip in 4 6; do "$probe" "$ip" udp 53 10123 allow; done
echo MNA_FIREWALL_PACKETS_OK
