"""Test the packaged default TUN on an explicitly selected, rooted x86_64 AVD."""
import argparse
import os
from pathlib import Path
import re
import socket
import struct
import threading

from android_guest import Guest
from android_tunnels import exact
from routing_apps import installed_clients


def tcp_peer(listener, observed):
    try:
        conn, _ = listener.accept()
        with conn:
            conn.settimeout(12)
            assert exact(conn, 3) == b"\x05\x01\x00"
            conn.sendall(b"\x05\x00")
            assert exact(conn, 4) == b"\x05\x01\x00\x01"
            host = socket.inet_ntoa(exact(conn, 4))
            port = struct.unpack("!H", exact(conn, 2))[0]
            observed.append(f"connect={host}:{port}")
            assert (host, port) == ("8.8.4.4", 19437)
            conn.sendall(bytes.fromhex("05000001000000000000"))
            payload = b"test-uid-route\x00"
            assert exact(conn, len(payload)) == payload
            observed.append("payload=received")
            # Echo without waiting for FIN to distinguish the return data
            # path from implementations that defer a TCP half-close.
            conn.sendall(payload)
            observed.append("echo=sent")
            if conn.recv(1) == b"":
                observed.append("fin=received")
    except (OSError, EOFError, AssertionError) as error:
        observed.append(f"peer_error={error!r}")


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
        with installed_clients(g, str(probe)) as clients, socket.socket() as server:
            uid, route_probe = clients[0]
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(18)
            port = int(g.adb("reverse", "tcp:0", f"tcp:{server.getsockname()[1]}"))
            try:
                g.sh("iptables -I " + block)
                try:
                    g.sh(ctl + f"configure socks5://127.0.0.1:{port}")
                    g.sh(ctl + "start")
                    status = set(g.sh(ctl + "status").splitlines())
                    assert {"configured_mode=tun", "effective_mode=tun", "state=running"} <= status, status
                    observed = []
                    task = threading.Thread(target=tcp_peer, args=(server, observed), daemon=True)
                    task.start()
                    try:
                        g.sh(route_probe)
                    finally:
                        task.join(20)
                        print(f"UID {uid}: {observed}", flush=True)
                    assert {"connect=8.8.4.4:19437", "payload=received", "echo=sent"} <= set(observed)
                except Exception as error:
                    error.add_note(g.sh(f"ip -4 rule show; ip -6 rule show; ip link show; "
                                        f"cat {g.path}/state/tun.log {g.path}/state/core.log 2>/dev/null; true"))
                    raise
                finally:
                    try:
                        g.sh(ctl + "stop")
                    finally:
                        g.sh("iptables -D " + block)
            finally:
                g.adb("reverse", "--remove", f"tcp:{port}")
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
