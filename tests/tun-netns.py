"""Exercise the default TUN data path in a newly created Linux network namespace.

Run as root with iproute2 and /dev/net/tun:
    python3 tests/tun-netns.py /path/to/magicbox /path/to/hev-socks5-tunnel
"""

import contextlib
import ctypes
import ipaddress
import os
from pathlib import Path
import shutil
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import tempfile
import threading
import time


MODULE = Path(__file__).resolve().parents[1] / "src/magicnet-astra-pro"
ADDRESS = ("1.1.1.1", "2606:4700:4700::1111")
PORT = 18495
PAYLOAD = b"MagicNet TUN packet"
REPLY = b"upstream received " + PAYLOAD


def open_namespace():
    if os.geteuid() != 0:
        sys.exit("TUN fixture needs root with CAP_SYS_ADMIN and CAP_NET_ADMIN")
    if not Path("/dev/net/tun").is_char_device():
        sys.exit("TUN fixture needs /dev/net/tun")
    # A mount namespace gives any sysfs readers the same interface view as ip.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.unshare(0x40000000 | 0x00020000) != 0:  # CLONE_NEWNET | CLONE_NEWNS
        raise OSError(ctypes.get_errno(), "unshare network and mount namespaces")
    subprocess.run(["mount", "--make-rprivate", "/"], check=True)
    subprocess.run(["mount", "-t", "sysfs", "sysfs", "/sys"], check=True)
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True)
    # A kernel route to an unconnected dummy link makes bypass after an
    # engine crash observable without an uplink or Internet access.
    subprocess.run(["ip", "link", "add", "fixture0", "type", "dummy"], check=True)
    subprocess.run(["ip", "link", "set", "fixture0", "up"], check=True)
    for af, address in (("-4", "192.0.2.1/24"), ("-6", "2001:db8:1::1/64")):
        args = ["ip", af, "address", "add", address, "dev", "fixture0"]
        subprocess.run(args + (["nodad"] if af == "-6" else []), check=True)
        subprocess.run(["ip", af, "route", "add", "default", "dev", "fixture0"], check=True)



def read_target(stream, kind):
    size = {1: 4, 4: 16}[kind]
    address = str(ipaddress.ip_address(stream.read(size)))
    port, = struct.unpack("!H", stream.read(2))
    assert address in ADDRESS and port == PORT, (address, port)


class Upstream(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(8)
        assert self.rfile.read(3) == bytes.fromhex("050100")
        self.wfile.write(bytes.fromhex("0500"))
        version, cmd, reserved, kind = self.rfile.read(4)
        assert (version, reserved) == (5, 0)
        if cmd == 1:
            read_target(self.rfile, kind)
            self.wfile.write(bytes.fromhex("05000001") + bytes(6))
            assert self.rfile.read(len(PAYLOAD)) == PAYLOAD
            assert self.rfile.read(1) == b"", "expected TCP write-half close"
            self.wfile.write(REPLY)
        else:
            assert cmd == 3 and kind == 1 and self.rfile.read(6) == bytes(6)
            relay_port = self.server.relay_port
            self.wfile.write(bytes.fromhex("050000017f000001") + struct.pack("!H", relay_port))
            # Retain the UDP association until the SOCKS client closes it.
            self.connection.settimeout(30)
            self.rfile.read(1)


class Datagram(socketserver.DatagramRequestHandler):
    def handle(self):
        assert self.rfile.read(3) == bytes(3)
        kind = self.rfile.read(1)[0]
        read_target(self.rfile, kind)
        offset = self.rfile.tell()
        assert self.rfile.read() == PAYLOAD
        self.wfile.write(self.packet[:offset] + REPLY)


def probe(host, family, protocol):
    """Run an ordinary unconfigured app socket as an Android-range UID."""
    source = """
import socket, sys
host, family, proto, port = sys.argv[1:]
with socket.socket(int(family), int(proto)) as connection:
    connection.settimeout(6)
    connection.connect((host, int(port)))
    connection.sendall(bytes.fromhex(sys.stdin.readline()))
    if int(proto) == socket.SOCK_STREAM:
        connection.shutdown(socket.SHUT_WR)
    expected = bytes.fromhex(sys.stdin.readline())
    result = connection.recv(4096)
    while result and len(result) < len(expected) and int(proto) == socket.SOCK_STREAM:
        part = connection.recv(4096)
        if not part:
            break
        result += part
    assert result == expected, result
"""
    subprocess.run(
        [sys.executable, "-c", source, host, str(int(family)), str(int(protocol)), str(PORT)],
        input=f"{PAYLOAD.hex()}\n{REPLY.hex()}\n", text=True, timeout=12, check=True,
        user=10123, group=10123, extra_groups=[], cwd="/",
    )


def rpdb():
    return tuple(subprocess.check_output(["ip", family, "rule", "show"]) for family in ("-4", "-6"))


def exercise(binary, tunnel):
    with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
        module, state = Path(tmp, "module"), Path(tmp, "state")
        shutil.copytree(MODULE, module)
        (module / "bin").mkdir(exist_ok=True)
        for name, path in (("magicbox", binary), ("hev-socks5-tunnel", tunnel)):
            shutil.copy(path, module / "bin" / name)
        (module / "rules").mkdir(exist_ok=True)
        (module / "rules/block.txt").write_text("magicbox-exact-v1\nblocked.example\n")
        env = {**os.environ, "MAGICNET_STATE_DIR": str(state)}

        def cli(*args, success=True, **extra_env):
            p = subprocess.run(["sh", module / "cli", *args], env={**env, **extra_env},
                               capture_output=True, text=True, timeout=25)
            assert (p.returncode == 0) == success, (args, p.returncode, p.stdout, p.stderr)
            return p.stdout.strip()

        def app_route(expected_device):
            for af, host in zip(("-4", "-6"), ADDRESS):
                result = subprocess.run(["ip", af, "route", "get", host, "uid", "10123"],
                                        text=True, capture_output=True)
                if expected_device:
                    assert result.returncode == 0 and f"dev {expected_device} " in result.stdout, result
                else:
                    assert result.returncode != 0, result
                    routes = subprocess.check_output(["ip", af, "route", "show", "table", "19871"], text=True)
                    assert any(line.startswith("unreachable default") for line in routes.splitlines()), routes

        def identity():
            return (state / "pid").read_bytes(), (state / "tun.pid").read_bytes(), rpdb()

        def stopped():
            app_route("fixture0")
            assert rpdb() == baseline
            assert not Path("/sys/class/net/magicnet0").exists()
            fields = cli("status").splitlines()
            assert {"effective_mode=off", "state=stopped", "autostart=no"} <= set(fields), fields
            assert not (state / "pid").exists()
            with socket.socket() as check:
                assert check.connect_ex(("127.0.0.1", 1080)) != 0

        relay = stack.enter_context(socketserver.UDPServer(("127.0.0.1", 0), Datagram))
        upstream = stack.enter_context(socketserver.ThreadingTCPServer(("127.0.0.1", 0), Upstream))
        upstream.daemon_threads = True
        upstream.relay_port = relay.server_address[1]
        for server in (relay, upstream):
            threading.Thread(target=server.serve_forever, daemon=True).start()
            stack.callback(server.shutdown)

        baseline = rpdb()
        stack.callback(cli, "stop")
        assert cli("mode") == "tun"
        cli("configure", f"socks5://127.0.0.1:{upstream.server_address[1]}")

        # Inject failure after IPv4 policy installation. Rollback must remove
        # its earlier effects and leave the working core socket closed.
        injected = Path(tmp, "injected")
        injected.mkdir()
        sentinel = injected / "hit"
        fake_ip = injected / "ip"
        real_ip = shutil.which("ip")
        fake_ip.write_text('#!/bin/sh\ncase " $* " in *" -6 rule add "*) '
                           ': > "$TUN_TEST_MARKER"; exit 42;; esac\nexec "$TUN_TEST_IP" "$@"\n')
        fake_ip.chmod(0o755)
        cli("start", success=False, PATH=f"{injected}:{env['PATH']}",
            TUN_TEST_MARKER=str(sentinel), TUN_TEST_IP=real_ip)
        assert sentinel.exists(), "start failed before IPv6 policy installation"
        stopped()

        for cycle in range(2):
            cli("start")
            assert {"state=running", "effective_mode=tun", "configured_mode=tun"} <= set(cli("status").splitlines())
            running = identity()
            cli("start")
            assert identity() == running
            app_route("magicnet0")
            for host, family in zip(ADDRESS, (socket.AF_INET, socket.AF_INET6)):
                for proto in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                    probe(host, family, proto)
            if cycle == 1:
                pid = int((state / "tun.pid").read_text().split()[0])
                assert os.path.samefile(f"/proc/{pid}/exe", module / "bin/hev-socks5-tunnel")
                os.kill(pid, signal.SIGKILL)
                for _ in range(100):
                    if not Path("/sys/class/net/magicnet0").exists():
                        break
                    time.sleep(0.02)
                assert not Path("/sys/class/net/magicnet0").exists()
                assert {"state=degraded", "effective_mode=degraded"} <= set(cli("status").splitlines())
                app_route(None)
            cli("stop")
            cli("stop")
            stopped()
    print("PASS default TUN: IPv4/IPv6 TCP and UDP via upstream, repeated start/stop, partial startup rollback, engine crash blocks bypass")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    binaries = [Path(path).resolve(strict=True) for path in sys.argv[1:]]
    open_namespace()
    exercise(*binaries)
