"""Exercise an Android app UID's unmodified TCP socket against a local test peer."""
import sys

from android_guest import Guest
from routing_apps import installed_clients


def main(module, probe):
    with Guest() as g, installed_clients(g, probe) as clients:
        (selected_uid, selected), (other_uid, other) = clients
        assert selected_uid != other_uid
        print(f"PackageManager assigned test UIDs {selected_uid} and {other_uid}", flush=True)
        g.adb("push", probe, g.path + "/probe")
        g.sh(f"chmod 755 {g.path}/probe")
        state = g.path + "/state"
        ctl = f"cd {g.quote(module)} && export MAGICNET_BUSYBOX=/data/local/tmp/busybox MAGICNET_STATE_DIR={g.quote(state)} && sh cli "
        g.sh(f"cd {g.path}; ./probe --upstream </dev/null >peer-log 2>&1 & echo $! >peer-pid")
        peer_port = int(g.sh(f"head -1 {g.path}/peer-log"))
        # Older AOSP kernels omit the dummy driver. An empty bridge or veth with
        # its peer down provides the same isolated egress for unmatched probes.
        g.sh("! ip link show mn-rt0 >/dev/null 2>&1 && ! ip link show mn-rt1 >/dev/null 2>&1")
        medium = g.sh("if ip link add mn-rt0 type dummy 2>/dev/null; then echo dummy; "
                      "elif ip link add mn-rt0 type bridge 2>/dev/null; then echo bridge; "
                      "elif ip link add mn-rt0 type veth peer name mn-rt1 2>/dev/null; then echo veth; "
                      "else echo 'no isolated virtual link available' >&2; exit 1; fi")
        print(f"isolated Android test link: {medium}", flush=True)
        try:
            g.sh("ip link set mn-rt0 up && ip addr add 192.0.2.222/32 dev mn-rt0 && "
                 "ip route add table 19437 8.8.4.4/32 dev mn-rt0 src 192.0.2.222 && "
                 "ip rule add pref 80 to 8.8.4.4/32 lookup 19437")
            route = g.sh("ip route get 8.8.4.4")
            assert "dev mn-rt0 " in route and "src 192.0.2.222" in route, route
            if medium == "bridge":
                assert not g.sh("ls -A /sys/class/net/mn-rt0/brif")
            g.sh(ctl + "mode local")
            g.sh(ctl + f"configure socks5://127.0.0.1:{peer_port}")
            g.sh(ctl + "start")
            g.sh(ctl + f"traffic apply uid:{selected_uid}")
            status = g.sh(ctl + "traffic status").splitlines()
            modes = [line for line in status if line in ("mode=dual-stack-redirect", "mode=ipv4-redirect-ipv6-block")]
            assert len(modes) == 1, status
            print(modes[0], flush=True)
            g.sh(selected)
            assert "ORIGINAL_DESTINATION_AND_FIN" in g.sh(f"cat {g.path}/peer-log")
            g.sh(f"{other}; case $? in 1|142) exit 0;; *) exit 1;; esac")
            g.sh(ctl + "traffic clear")
            g.sh(f"{selected}; case $? in 1|142) exit 0;; *) exit 1;; esac")
        except Exception as error:
            audit = g.sh("ip -4 rule show; ip route get 8.8.4.4; iptables -t nat -nvxL MNAP_TCP_OUTPUT; "
                         f"cat {g.path}/state/redirect.log 2>/dev/null; cat {g.path}/state/core.log 2>/dev/null; true")
            error.add_note(audit)
            raise
        finally:
            g.sh(ctl + "traffic clear >/dev/null 2>&1 || true")
            g.sh(ctl + "stop >/dev/null 2>&1 || true")
            g.sh("ip rule del pref 80 to 8.8.4.4/32 lookup 19437; ip link del mn-rt0")
            g.sh(f"kill $(cat {g.path}/peer-pid) 2>/dev/null || true")
        print("ANDROID_APP_TCP_PASS: selected UID and original destination, unselected app bypass, cleanup, TCP half-close")


if __name__ == "__main__":
    main(*sys.argv[1:])
