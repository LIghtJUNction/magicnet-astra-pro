"""Exercise the packaged CLI and its actual REDIRECT / DNS rules in offline namespaces."""
import contextlib
import os
from pathlib import Path
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading

HERE = Path(__file__).resolve()
PUBLIC = ("1.1.1.1", "2606:4700:4700::1111")
PORT = 18495
REACHABLE = "2606:4700:4700::42"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, timeout=20, **kwargs)


def client(host, expected):
    try:
        with socket.create_connection((host, PORT), timeout=1.25) as peer:
            data = peer.recv(64).decode()
    except OSError:
        data = "unreachable"
    if data != expected:
        raise AssertionError((host, expected, data))


def exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise EOFError("short SOCKS5 request")
        data.extend(chunk)
    return data


def fake_proxy(sock, errors):
    while True:
        try:
            peer, _ = sock.accept()
            with peer:
                peer.settimeout(4)
                assert exact(peer, 3) == bytes.fromhex("050100")
                peer.sendall(bytes.fromhex("0500"))
                version, cmd, _, atyp = exact(peer, 4)
                assert (version, cmd) == (5, 1)
                family, size = {1: (socket.AF_INET, 4), 4: (socket.AF_INET6, 16)}[atyp]
                address = socket.inet_ntop(family, exact(peer, size))
                assert int.from_bytes(exact(peer, 2), "big") == PORT
                peer.sendall(bytes.fromhex("05000001") + bytes(6) + address.encode())
        except BaseException as exc:
            errors.append(exc)
            return


def uid_check(uid, host, expected):
    run(sys.executable, "-", "probe", host, expected, input=HERE.read_bytes(),
        cwd="/", user=uid, group=uid, extra_groups=[])


def direct_server():
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as server:
        server.bind((REACHABLE, PORT))
        server.listen()
        print("ready", flush=True)
        while True:
            peer, _ = server.accept()
            with peer:
                peer.sendall(b"direct")


def named_node(ctl, tmp, client_ns, numeric):
    address = "93.184.216.34"
    run("ip", "-n", client_ns, "addr", "add", address + "/32", "dev", "lo")
    run("ip", "route", "add", address, "via", "192.168.70.2", "dev", "hot0")
    def openssl(*args):
        run("openssl", *args, cwd=tmp, capture_output=True)

    openssl("req", "-x509", "-nodes", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
            "-days", "1", "-subj", "/CN=Fixture CA", "-addext", "basicConstraints=critical,CA:TRUE",
            "-keyout", "ca.key", "-out", "ca.pem")
    openssl("req", "-new", "-nodes", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
            "-subj", "/CN=resolver.example", "-keyout", "key", "-out", "csr")
    (Path(tmp) / "ext").write_text("basicConstraints=critical,CA:FALSE\nsubjectAltName=DNS:resolver.example\n")
    openssl("x509", "-req", "-in", "csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
            "-days", "1", "-extfile", "ext", "-out", "cert")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(Path(tmp, "cert"), Path(tmp, "key"))
    seen = []
    with socket.socket() as dns, subprocess.Popen(
            ["ip", "netns", "exec", client_ns, sys.executable, HERE, "node-server", address],
            stdout=subprocess.PIPE, text=True) as server:
        try:
            assert server.stdout.readline().strip() == "ready"
            dns.bind(("127.0.0.1", 0))
            dns.listen()
            def answer():
                for _ in range(2):  # one scoped redirect service, one mixed service
                    stream, _ = dns.accept()
                    with context.wrap_socket(stream, server_side=True) as peer:
                        for kind in (1, 28):
                            query = exact(peer, int.from_bytes(exact(peer, 2), "big"))
                            assert query[12:] == b"\x04node\x07example\x00" + struct.pack("!HH", kind, 1)
                            seen.append(kind)
                            records = 1 if kind == 1 else 0
                            data = query[:2] + struct.pack("!HHHHH", 0x8180, 1, records, 0, 0) + query[12:]
                            if records:
                                data += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 30, 4) + socket.inet_aton(address)
                            peer.sendall(len(data).to_bytes(2, "big") + data)
            threading.Thread(target=answer, daemon=True).start()
            ctl("configure", f"socks5://node.example:{PORT}", overrides={
                "MAGICBOX_CA_BUNDLE": str(Path(tmp, "ca.pem")),
                "MAGICBOX_RESOLVER": f"tls://127.0.0.1:{dns.getsockname()[1]}?server_name=resolver.example"})
            assert seen == [1, 28, 1, 28]
            uid_check(10123, PUBLIC[0], PUBLIC[0])
            assert "node.example" not in subprocess.check_output(["iptables", "-t", "nat", "-S"], text=True)
            # The numeric peer pinned from DoT is refused as a proxy destination.
            uid_check(10123, address, "")
            ctl("configure", numeric)
        finally:
            server.terminate()


def fallback(ctl, tmp, client_ns):
    # A reachable IPv6 peer distinguishes a working filter from a missing
    # route. The origin has no external interfaces.
    run("ip", "-6", "-n", client_ns, "addr", "add", REACHABLE + "/128", "dev", "lo", "nodad")
    run("ip", "-6", "route", "add", REACHABLE, "via", "fd00:70::2", "dev", "hot0")
    shim = Path(tmp) / "no-v6-nat"
    shim.mkdir()
    (shim / "ip6tables").write_text(
        "#!/bin/sh\nif [ \"$*\" = '-t nat -S' ]; then echo 'Table does not exist' >&2; exit 3; fi\n"
        f"exec {shutil.which('ip6tables')} \"$@\"\n")
    (shim / "ip6tables").chmod(0o755)
    overrides = {"PATH": f"{shim}:{os.environ['PATH']}"}
    with subprocess.Popen(["ip", "netns", "exec", client_ns, sys.executable, HERE, "direct"],
                          stdout=subprocess.PIPE, text=True) as server:
        try:
            assert server.stdout.readline().strip() == "ready"
            uid_check(10123, REACHABLE, "direct")
            ctl("traffic", "apply", "uid:10123", "tether:hot0", overrides=overrides)
            assert "mode=ipv4-redirect-ipv6-block" in ctl("traffic", "status")
            uid_check(10123, PUBLIC[0], PUBLIC[0])
            uid_check(10123, REACHABLE, "unreachable")
            uid_check(10124, REACHABLE, "direct")
            uid_check(0, REACHABLE, "direct")
            run("ip6tables", "-C", "MNAP_RGD_FORWARD", "-i", "hot0", "-p", "tcp", "-j", "DROP")
            ctl("traffic", "clear", overrides=overrides)
            uid_check(10123, REACHABLE, "direct")
        finally:
            server.terminate()


def router(root, binary, ns):
    with tempfile.TemporaryDirectory() as tmp, socket.socket() as proxy:
        folder = Path(tmp) / "module"
        shutil.copytree(root, folder)
        (folder / "bin").mkdir(exist_ok=True)
        shutil.copyfile(binary, folder / "bin/magicbox")
        (folder / "bin/magicbox").chmod(0o755)
        (folder / "rules").mkdir(exist_ok=True)
        (folder / "rules/block.txt").write_text("magicbox-exact-v1\nblocked.example\n")
        state = Path(tmp) / "state"
        env = {**os.environ, "MAGICNET_STATE_DIR": str(state)}
        def ctl(*cmd, ok=True, overrides=None):
            result = subprocess.run(["sh", str(folder / "cli"), *cmd], capture_output=True,
                                    timeout=22, text=True, env={**env, **(overrides or {})})
            assert (result.returncode == 0) == ok, (cmd, result.stdout, result.stderr)
            return result.stdout
        proxy.bind(("127.0.0.1", 0))
        proxy.listen()
        errors = []
        threading.Thread(target=fake_proxy, args=(proxy, errors), daemon=True).start()
        ctl("mode", "local")
        ctl("configure", f"socks5://127.0.0.1:{proxy.getsockname()[1]}")
        ctl("start")
        try:
            for fw in ("iptables", "ip6tables"):
                run(fw, "-t", "nat", "-N", "OTHER_APP")
                run(fw, "-t", "nat", "-A", "OUTPUT", "-j", "OTHER_APP")
            ctl("dns", "apply", "uid:10129")
            ctl("traffic", "apply", "uid:0", ok=False)
            ctl("traffic", "apply", "uid:101000", ok=False)
            ctl("traffic", "apply", "tether:tailscale0", ok=False)
            ctl("traffic", "apply", "uid:10123", "tether:hot0")
            ctl("traffic", "sync")
            for host in PUBLIC:
                uid_check(10123, host, host)
                uid_check(10124, host, "unreachable")
                uid_check(0, host, "unreachable")
                run("ip", "netns", "exec", ns, sys.executable, HERE, "probe", host, host)

            # A route using a conventional VPN interface bypasses OUTPUT interception.
            run("ip", "link", "add", "tun9", "type", "veth", "peer", "name", "vpn-peer")
            run("ip", "link", "set", "tun9", "up")
            run("ip", "link", "set", "vpn-peer", "up")
            run("ip", "route", "add", "8.8.8.8", "dev", "tun9")
            uid_check(10123, "8.8.8.8", "unreachable")

            # Change upstream to a different numeric address. Its packets retain normal routing.
            ctl("configure", "socks5://1.1.1.1:44090")
            for fw in ("iptables", "ip6tables"):
                run(fw, "-C", "MNAP_RGD_OUTPUT", "-m", "owner", "--uid-owner", "10123", "-p", "udp", "--dport", "53", "-j", "DROP")
                run(fw, "-C", "MNAP_RGD_FORWARD", "-i", "hot0", "-p", "tcp", "--dport", "853", "-j", "DROP")
            run("iptables", "-t", "nat", "-C", "MNAP_TCP_OUTPUT", "-d", "1.1.1.1", "-j", "RETURN")
            ctl("configure", f"socks5://127.0.0.1:{proxy.getsockname()[1]}")
            uid_check(10123, PUBLIC[0], PUBLIC[0])
            named_node(ctl, tmp, ns, f"socks5://127.0.0.1:{proxy.getsockname()[1]}")
            fail = Path(tmp) / "fail"
            fail.mkdir()
            (fail / "ip6tables-restore").write_text(
                "#!/bin/sh\nf=$(mktemp); cat > \"$f\"\n"
                "if grep -q 'uid-owner 10124.*REDIRECT' \"$f\"; then rm -f \"$f\"; exit 42; fi\n"
                f"{shutil.which('ip6tables-restore')} \"$@\" < \"$f\"; code=$?; rm -f \"$f\"; exit $code\n")
            (fail / "ip6tables-restore").chmod(0o755)
            ctl("traffic", "apply", "uid:10124", ok=False, overrides={"PATH": f"{fail}:{env['PATH']}"})
            assert "uid 10123" in ctl("traffic", "status")
            uid_check(10123, PUBLIC[0], PUBLIC[0])
            for fw in ("iptables", "ip6tables"):
                run(fw, "-C", "MNAP_RGD_OUTPUT", "-m", "owner", "--uid-owner", "10123", "-p", "udp", "--dport", "53", "-j", "DROP")
            ctl("stop")
            assert "redirect=stopped" in ctl("traffic", "status")
            uid_check(10123, PUBLIC[0], "unreachable")
            ctl("start")
            uid_check(10123, PUBLIC[1], PUBLIC[1])
            ctl("traffic", "clear")
            assert "scope=empty" in ctl("traffic", "status")
            for fw in ("iptables", "ip6tables"):
                run(fw, "-t", "nat", "-C", "OUTPUT", "-j", "OTHER_APP")
                run(fw, "-C", "MNAP_DNS_OUTPUT", "-m", "owner", "--uid-owner", "10129", "-p", "udp", "--dport", "53", "-j", "DROP")
                for table in ("filter", "nat"):
                    snapshot = subprocess.check_output([fw, "-t", table, "-S"], text=True)
                    assert "MNAP_TCP" not in snapshot and "MNAP_RGD" not in snapshot
            fallback(ctl, tmp, ns)
            if errors:
                raise errors[0]
        finally:
            ctl("uninstall")


def main(root, binary):
    with contextlib.ExitStack() as cleanup:
        router_ns, client_ns = (f"mna-{x}-{os.getpid()}" for x in ("r", "c"))
        for ns in (router_ns, client_ns):
            run("ip", "netns", "add", ns)
            cleanup.callback(run, "ip", "netns", "del", ns)
            run("ip", "-n", ns, "link", "set", "lo", "up")
        run("ip", "-n", router_ns, "link", "add", "hot0", "type", "veth", "peer", "name", "client0", "netns", client_ns)
        for ns, device, num in ((router_ns, "hot0", 1), (client_ns, "client0", 2)):
            run("ip", "-n", ns, "link", "set", device, "up")
            run("ip", "-n", ns, "addr", "add", f"192.168.70.{num}/24", "dev", device)
            run("ip", "-6", "-n", ns, "addr", "add", f"fd00:70::{num}/64", "dev", device, "nodad")
        for af, host, via in (("-4", PUBLIC[0], "192.168.70.1"), ("-6", PUBLIC[1], "fd00:70::1")):
            run("ip", af, "-n", router_ns, "route", "add", host, "dev", "hot0")
            run("ip", af, "-n", client_ns, "route", "add", host, "via", via)
        subprocess.run(
            ["ip", "netns", "exec", router_ns, sys.executable, HERE, "router", root, binary, client_ns],
            timeout=160, check=True)
    print("PASS selected UID and tether IPv4/IPv6 flows, root and adjacent UID, VPN-interface bypass, upstream refresh, DNS rules, rollback, lifecycle and foreign chain ownership; no-IPv6-NAT fallback blocked selected IPv6 TCP against a reachable peer while IPv4 still proxied; named node authenticated DNS and pinned-peer denial")


if __name__ == "__main__":
    if sys.argv[1] == "node-server":
        with socket.socket() as server:
            server.bind((sys.argv[2], PORT))
            server.listen()
            print("ready", flush=True)
            failures = []
            fake_proxy(server, failures)
            raise failures[0]
    elif sys.argv[1] == "direct":
        direct_server()
    elif sys.argv[1] == "probe":
        client(*sys.argv[2:])
    elif sys.argv[1] == "router":
        router(*sys.argv[2:])
    else:
        main(*(str(Path(p).resolve()) for p in sys.argv[1:]))
