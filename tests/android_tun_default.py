"""Test the packaged default TUN on an explicitly selected, rooted x86_64 AVD."""
import argparse
from contextlib import ExitStack
from difflib import unified_diff
import os
from pathlib import Path
import re
import time

from android_guest import Guest
from routing_apps import installed_clients, start_selected_activity


def rules(g):
    return {af: g.sh(f"ip {af} rule show").splitlines() for af in ("-4", "-6")}


def diff_rules(before, after):
    return "\n".join(line for af in before for line in
                     unified_diff(before[af], after[af], f"{af} before", f"{af} after", lineterm=""))


def tun_counters(g, cleanup):
    # Targetless rules count TUN packets and continue normal traversal.
    for tool in ("iptables", "ip6tables"):
        for chain, direction in (("PREROUTING", "-i"), ("POSTROUTING", "-o")):
            rule = f"{chain} {direction} magicnet0"
            reply = g.sh(f"if {tool} -t mangle -I {rule}; then echo installed; fi")
            if "installed" in reply.splitlines():
                cleanup.callback(g.sh, f"{tool} -t mangle -D {rule}")


def tun_snapshot(g, uid):
    return g.sh(f"""
        ip -s address show dev magicnet0
        for af in -4 -6; do
            echo "== $af rules and TUN routes =="
            ip $af rule show; ip $af route show table 19871
        done
        echo '== IPv4 app UID route =='; ip -4 route get 8.8.4.4 uid {uid}
        for f in /proc/sys/net/ipv4/conf/all/rp_filter /proc/sys/net/ipv4/conf/magicnet0/rp_filter; do
            echo "$f"; cat "$f"
        done
        for tool in iptables ip6tables; do
            for chain in PREROUTING POSTROUTING; do
                echo "== $tool $chain TUN packet and byte counters =="
                $tool -t mangle -nvxL "$chain" | grep -E 'pkts|magicnet0'
            done
        done
        echo '== fixture bypass rejects =='; iptables -nvxL OUTPUT | grep -E 'pkts|19437'
        for f in {g.path}/peer.log {g.path}/state/tun.log {g.path}/state/core.log; do
            echo "== $f =="; tail -n 40 "$f"
        done
        true
    """)


def exercise(serial, archive, busybox, probe):
    if not re.fullmatch(r"emulator-[0-9]+", serial):
        raise ValueError("select an emulator-NNNN serial")
    os.environ["ANDROID_SERIAL"] = serial
    with Guest() as g:
        assert g.sh("id -u") == "0", "run adb root on this disposable emulator"
        assert g.sh("getprop ro.product.cpu.abi") == "x86_64"
        g.adb("push", str(archive), g.path + "/module.zip")
        g.adb("push", str(busybox), g.path + "/busybox")
        g.sh(f'cd {g.path} && chmod 755 busybox && mkdir module && cd module && '
             '../busybox unzip -oq ../module.zip && chmod 755 cli bin/*')
        ctl = (f'cd {g.path}/module && export MAGICNET_BUSYBOX={g.path}/busybox '
               f'MAGICNET_STATE_DIR={g.path}/state && sh cli ')
        families = ("-4", "-6")
        before_apks = rules(g)
        assert "magicnet0" not in g.sh("ip link show")
        assert g.sh(ctl + "mode") == "tun"

        # Even a failing probe cannot leave the emulator on a physical uplink.
        block = "OUTPUT ! -o magicnet0 -p tcp -d 8.8.4.4/32 --dport 19437 -j REJECT"
        g.sh("iptables -C " + block, success=False)
        with installed_clients(g, str(probe), selected_activity=True) as clients, ExitStack() as sentinels:
            after_install = rules(g)
            change = diff_rules(before_apks, after_install)
            if change:
                print("RPDB during APK installation:\n" + change, flush=True)
            for af, destination in (("-4", "192.0.2.247/32"), ("-6", "2001:db8::f247/128")):
                assert not any(line.startswith("9801:") for line in after_install[af])
                args = f"pref 9801 to {destination} lookup 19878"
                g.sh(f"ip {af} rule add {args}")
                sentinels.callback(g.sh, f"ip {af} rule del {args}")
            uid, route_probe = clients[0]
            g.adb("push", str(probe), g.path + "/peer")
            g.sh(f"cd {g.path} && chmod 755 peer && "
                 "(./peer --upstream </dev/null >peer.log 2>&1 & echo $! >peer.pid)")
            try:
                for _ in range(40):
                    port = g.sh(f"head -1 {g.path}/peer.log")
                    if port.isdecimal() and 0 < int(port) <= 65535:
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("guest SOCKS fixture did not start")
                g.sh("iptables -I " + block)
                try:
                    baseline = rules(g)
                    for lines in baseline.values():
                        assert any(line.startswith("9801:") and "lookup 19878" in line for line in lines), lines
                    g.sh(ctl + f"configure socks5://127.0.0.1:{port}")
                    g.sh(ctl + "start")
                    print(f"Fixture UID {uid} start state: " + g.sh(f"am get-uid-state {uid}"), flush=True)
                    if not os.environ.get("ASTRA_CI_BACKGROUND_CONTROL"):
                        start_selected_activity(g, uid)
                    status = set(g.sh(ctl + "status").splitlines())
                    assert {"configured_mode=tun", "effective_mode=tun", "state=running"} <= status, status
                    # Both sockets belong to this guest. The synthetic upstream
                    # waits for the application's FIN before returning its echo.
                    tun_counters(g, sentinels)
                    print("TUN counters before app socket:\n" + g.sh("ip -s link show dev magicnet0"), flush=True)
                    g.sh(route_probe)
                    evidence = g.sh(f"cat {g.path}/peer.log").splitlines()
                    assert "ORIGINAL_DESTINATION_AND_FIN" in evidence, evidence
                    print(f"UID {uid}: original target, request payload, FIN and return echo", flush=True)
                except Exception as error:
                    try:
                        error.add_note(tun_snapshot(g, uid))
                    except Exception as diagnostic_error:
                        error.add_note(f"Failed to capture TUN diagnostics: {diagnostic_error}")
                    raise
                finally:
                    try:
                        g.sh(ctl + "stop")
                    finally:
                        g.sh("iptables -D " + block)
            finally:
                g.sh(f'pid=$(cat {g.path}/peer.pid); '
                     f'if [ "$(readlink /proc/$pid/exe)" = {g.path}/peer ]; then kill "$pid"; fi')
            after_stop = rules(g)
            delta = diff_rules(baseline, after_stop)
            assert not delta, "RPDB changed between module configure and stop:\n" + delta
            assert "magicnet0" not in g.sh("ip link show")
            for af in families:
                assert not any(line.startswith("9000:") for line in after_stop[af])
                assert not re.search(r"\btable 19871\b", g.sh(f"ip {af} route show table all"))
        after_apks = rules(g)
        change = diff_rules(before_apks, after_apks)
        if change:
            print("RPDB outside module lifetime (APK install/uninstall):\n" + change, flush=True)
        assert {"effective_mode=off", "state=stopped", "autostart=no"} <= set(g.sh(ctl + "status").splitlines())
        print("ANDROID_DEFAULT_TUN_PASS: new-install mode, app UID TCP payload and return path, dual-stack policy cleanup")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="rooted disposable emulator-NNNN")
    for arg in ("archive", "busybox", "probe"):
        parser.add_argument("--" + arg, type=Path, required=True)
    exercise(**vars(parser.parse_args()))
