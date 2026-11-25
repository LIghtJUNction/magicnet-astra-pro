#!/system/bin/sh
set -eu
[ "$(getprop ro.kernel.qemu)" = 1 ] && [ "$(id -u)" = 0 ]
root=${MAGICNET_MODULE_DIR:-/data/local/tmp/mna-install}
export MAGICNET_STATE_DIR=/data/local/tmp/mna-firewall-qa
if [ -x /data/local/tmp/busybox ]; then export MAGICNET_BUSYBOX=/data/local/tmp/busybox; fi
xt() {
    retries=0
    while :; do
        "$@" 2> /data/local/tmp/mna-firewall-qa.err && return 0
        if [ "$retries" -ge 32 ] || ! grep -i 'xtables lock' /data/local/tmp/mna-firewall-qa.err >/dev/null; then
            cat /data/local/tmp/mna-firewall-qa.err >&2
            return 1
        fi
        retries=$((retries+1))
        sleep 0.15
    done
}
ctl() { sh "$root/cli" dns "$@"; }
cleanup() {
    ctl clear >/dev/null 2>&1 || :
    for fw in iptables ip6tables; do
        xt "$fw" -D MNA_QA_FOREIGN -j RETURN 2>/dev/null || :
        xt "$fw" -X MNA_QA_FOREIGN 2>/dev/null || :
    done
    rm -f /data/local/tmp/mna-firewall-qa.err
}
# Distinctive QA chain checks isolation; bail out if it already exists.
for fw in iptables ip6tables; do
    if xt "$fw" -S MNA_QA_FOREIGN >/dev/null 2>&1; then exit 1; fi
done
trap cleanup EXIT
for fw in iptables ip6tables; do
    xt "$fw" -N MNA_QA_FOREIGN
    xt "$fw" -A MNA_QA_FOREIGN -j RETURN
done
ctl apply uid:10123 tether:mn-qa0
ctl apply uid:10123 tether:mn-qa0
for fw in iptables ip6tables; do
    for proto in tcp udp; do
        for port in 53 853; do
            xt "$fw" -C MNAP_DNS_OUTPUT -m owner --uid-owner 10123 -p "$proto" --dport "$port" -j DROP
            for hook in INPUT FORWARD; do
                xt "$fw" -C "MNAP_DNS_$hook" -i mn-qa0 -p "$proto" --dport "$port" -j DROP
            done
        done
    done
    for hook in OUTPUT INPUT FORWARD; do
        [ "$(xt "$fw" -S "$hook" | grep -c -- "-A $hook -j MNAP_DNS_$hook")" -eq 1 ]
    done
done
if ctl apply 'tether:wlan+'; then exit 1; fi
ctl apply uid:10124
for fw in iptables ip6tables; do
    xt "$fw" -C MNAP_DNS_OUTPUT -m owner --uid-owner 10124 -p udp --dport 53 -j DROP
    if xt "$fw" -C MNAP_DNS_OUTPUT -m owner --uid-owner 10123 -p udp --dport 53 -j DROP; then exit 1; fi
    if xt "$fw" -S MNAP_DNS_FORWARD >/dev/null 2>&1; then exit 1; fi
done
ctl clear
for fw in iptables ip6tables; do
    xt "$fw" -C MNA_QA_FOREIGN -j RETURN
    if xt "$fw" -S MNAP_DNS_OUTPUT >/dev/null 2>&1; then exit 1; fi
done
echo MNA_FIREWALL_TEST_OK
