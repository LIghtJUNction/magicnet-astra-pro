"""Exercise an Android app UID's unmodified TCP socket against a local test peer."""
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

from android_guest import Guest
from android_tunnels import exact


def peer(server):
    remote, _ = server.accept()
    with remote:
        remote.settimeout(10)
        assert exact(remote, 3) == b"\x05\x01\0"
        remote.sendall(b"\x05\0")
        command = exact(remote, 10)
        assert command == b"\x05\x01\0\x01" + socket.inet_aton("8.8.4.4") + (19437).to_bytes(2, "big")
        remote.sendall(b"\x05\0\0\x01" + bytes(6))
        proof = b"test-uid-route\0"
        assert exact(remote, len(proof)) == proof and remote.recv(1) == b""
        remote.sendall(proof)


def main(module, probe):
    with Guest() as g, socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(15)
        g.adb("push", probe, g.path + "/probe")
        g.sh(f"chmod 755 {g.path}/probe")
        state = g.path + "/state"
        ctl = f"cd {g.quote(module)} && export MAGICNET_BUSYBOX=/data/local/tmp/busybox MAGICNET_STATE_DIR={g.quote(state)} && sh cli "
        g.adb("reverse", "tcp:19434", f"tcp:{server.getsockname()[1]}")
        # The only route for the test destination is an isolated dummy interface.
        # Keep it local even if a CI emulator has a real network uplink.
        g.sh("ip link add mn-rt0 type dummy")
        try:
            g.sh("ip link set mn-rt0 up && ip addr add 192.0.2.222/32 dev mn-rt0 && "
                 "ip route add table 19437 8.8.4.4/32 dev mn-rt0 src 192.0.2.222 && "
                 "ip rule add pref 80 to 8.8.4.4/32 lookup 19437")
            g.sh(ctl + "configure socks5://127.0.0.1:19434")
            g.sh(ctl + "start")
            g.sh(ctl + "traffic apply uid:10123")
            status = g.sh(ctl + "traffic status").splitlines()
            modes = [line for line in status if line in ("mode=dual-stack-redirect", "mode=ipv4-redirect-ipv6-block")]
            assert len(modes) == 1, status
            print(modes[0], flush=True)
            with ThreadPoolExecutor(max_workers=1) as e:
                received = e.submit(peer, server)
                g.sh(f"{g.path}/probe selected")
                received.result()
            g.sh(f"{g.path}/probe other; case $? in 1|142) exit 0;; *) exit 1;; esac")
            g.sh(ctl + "traffic clear")
            g.sh(f"{g.path}/probe selected; case $? in 1|142) exit 0;; *) exit 1;; esac")
        finally:
            g.sh(ctl + "traffic clear >/dev/null 2>&1 || true")
            g.sh(ctl + "stop >/dev/null 2>&1 || true")
            g.sh("ip rule del pref 80 to 8.8.4.4/32 lookup 19437; ip link del mn-rt0")
            g.adb("reverse", "--remove", "tcp:19434")
        print("ANDROID_APP_TCP_PASS: selected UID and original destination, adjacent UID bypass, cleanup, TCP half-close")


if __name__ == "__main__":
    main(*sys.argv[1:])
