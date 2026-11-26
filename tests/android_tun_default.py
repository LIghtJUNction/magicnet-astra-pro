"""Test the packaged default TUN on an explicitly selected, rooted x86_64 AVD."""
import argparse
import os
from pathlib import Path
import re
import time

from android_guest import Guest
from routing_apps import installed_clients


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
        baseline = [g.sh(f"ip {af} rule show") for af in families]
        assert "magicnet0" not in g.sh("ip link show")
        assert g.sh(ctl + "mode") == "tun"

        # Even a failing probe cannot leave the emulator on a physical uplink.
        block = "OUTPUT ! -o magicnet0 -p tcp -d 8.8.4.4/32 --dport 19437 -j REJECT"
        g.sh("iptables -C " + block, success=False)
        with installed_clients(g, str(probe)) as clients:
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
                    g.sh(ctl + f"configure socks5://127.0.0.1:{port}")
                    g.sh(ctl + "start")
                    status = set(g.sh(ctl + "status").splitlines())
                    assert {"configured_mode=tun", "effective_mode=tun", "state=running"} <= status, status
                    # Both sockets belong to this guest. The synthetic upstream
                    # waits for the application's FIN before returning its echo.
                    g.sh(route_probe)
                    evidence = g.sh(f"cat {g.path}/peer.log").splitlines()
                    assert "ORIGINAL_DESTINATION_AND_FIN" in evidence, evidence
                    print(f"UID {uid}: original target, request payload, FIN and return echo", flush=True)
                except Exception as error:
                    error.add_note(g.sh(f"ip -4 rule show; ip -6 rule show; ip link show; "
                                        f"cat {g.path}/peer.log {g.path}/state/tun.log "
                                        f"{g.path}/state/core.log 2>/dev/null; true"))
                    raise
                finally:
                    try:
                        g.sh(ctl + "stop")
                    finally:
                        g.sh("iptables -D " + block)
            finally:
                g.sh(f'pid=$(cat {g.path}/peer.pid); '
                     f'if [ "$(readlink /proc/$pid/exe)" = {g.path}/peer ]; then kill "$pid"; fi')
        assert baseline == [g.sh(f"ip {af} rule show") for af in families]
        assert "magicnet0" not in g.sh("ip link show")
        for af in families:
            assert not re.search(r"\btable 19871\b", g.sh(f"ip {af} route show table all"))
        assert {"effective_mode=off", "state=stopped", "autostart=no"} <= set(g.sh(ctl + "status").splitlines())
        print("ANDROID_DEFAULT_TUN_PASS: new-install mode, app UID TCP payload and return path, dual-stack policy cleanup")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="rooted disposable emulator-NNNN")
    for arg in ("archive", "busybox", "probe"):
        parser.add_argument("--" + arg, type=Path, required=True)
    exercise(**vars(parser.parse_args()))
