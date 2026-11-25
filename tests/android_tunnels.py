"""Exercise the actual KAM ZIP on an Android emulator with synthetic upstreams."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import zipfile
from android_guest import Guest

DOMAIN = "no-local-resolution.invalid"
PAYLOAD = bytes(range(256)) * 1024


def exact(sock, count):
    out = bytearray()
    while len(out) < count:
        chunk = sock.recv(count - len(out))
        if not chunk:
            raise EOFError("unexpected end of stream")
        out.extend(chunk)
    return bytes(out)


def headers(sock):
    data = bytearray()
    while not data.endswith(b"\r\n\r\n"):
        data += exact(sock, 1)
        if len(data) > 8192:
            raise ValueError("oversized header")
    return bytes(data)


def run(archive, busybox):
    with zipfile.ZipFile(archive) as z:
        blocked = z.read("rules/block.txt").decode().splitlines()[1]
    with Guest() as guest, tempfile.TemporaryDirectory() as tmp, socket.socket() as upstream:
        api = guest.sh("getprop ro.build.version.sdk")
        abi = guest.sh("getprop ro.product.cpu.abi")
        ctl = f"cd {guest.path} && export MAGICNET_BUSYBOX={guest.path}/busybox MAGICNET_STATE_DIR={guest.path}/state MAGICBOX_CA_BUNDLE={guest.path}/ca.pem && sh cli "
        guest.adb("push", str(archive), f"{guest.path}/candidate.zip")
        guest.adb("push", str(busybox), f"{guest.path}/busybox")
        guest.sh(f"cd {guest.path} && chmod 755 busybox && ./busybox unzip -oq candidate.zip && chmod 755 cli bin/magicbox")
        cert = Path(tmp, "ca.pem")
        key = Path(tmp, "key.pem")
        def openssl(*args):
            subprocess.run(["openssl", *args], check=True, capture_output=True, timeout=20)
        cakey = Path(tmp, "ca.key")
        csr = Path(tmp, "server.csr")
        leaf = Path(tmp, "server.pem")
        ext = Path(tmp, "extensions")
        ext.write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:relay.test\n")
        openssl("req","-x509","-newkey","ec","-pkeyopt","ec_paramgen_curve:P-256",
                "-nodes","-days","2","-subj","/CN=Test CA","-addext","basicConstraints=critical,CA:TRUE",
                "-keyout",cakey,"-out",cert)
        openssl("req","-new","-newkey","ec","-pkeyopt","ec_paramgen_curve:P-256",
                "-nodes","-subj","/CN=relay.test","-keyout",key,"-out",csr)
        openssl("x509","-req","-in",csr,"-CA",cert,"-CAkey",cakey,"-CAcreateserial",
                "-days","2","-extfile",ext,"-out",leaf)
        guest.adb("push", str(cert), f"{guest.path}/ca.pem")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(leaf, key)
        upstream.bind(("127.0.0.1", 0))
        upstream.listen()
        upstream.settimeout(20)
        port = upstream.getsockname()[1]
        guest.adb("reverse", "tcp:19443", f"tcp:{port}")
        local = int(guest.adb("forward","tcp:0","tcp:1080"))
        observed = []
        errors = []

        def relay():
            try:
                for _ in range(2):
                    c, _ = upstream.accept()
                    with c, context.wrap_socket(c,server_side=True) as tls:
                        tls.settimeout(15)
                        head = headers(tls)
                        assert head.startswith(f"CONNECT {DOMAIN}:443 HTTP/1.1\r\n".encode()), head
                        tls.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
                        assert exact(tls, len(PAYLOAD)) == PAYLOAD
                        tls.sendall(PAYLOAD[::-1])
                        observed.append(tls.version())
            except Exception as e:
                errors.append(e)

        worker = threading.Thread(target=relay, daemon=True)
        worker.start()
        try:
            assert "no_upstream" in guest.sh(ctl + "start", success=False)
            endpoint = "'https://127.0.0.1:19443?server_name=relay.test'"
            guest.sh(ctl + "configure " + endpoint)
            guest.sh(ctl + "start")
            assert "state=running" in guest.sh(ctl + "status")
            pid = guest.sh(f"cat {guest.path}/state/pid")
            guest.sh(ctl + "configure " + endpoint)
            guest.sh(ctl + "configure socks5://bad..name:42", success=False)
            assert pid == guest.sh(f"cat {guest.path}/state/pid")
            for proto in ["http", "socks"]:
                with socket.create_connection(("127.0.0.1",local),timeout=20) as client:
                    if proto == "http":
                        client.sendall(f"CONNECT {DOMAIN}:443 HTTP/1.1\r\nHost: {DOMAIN}:443\r\n\r\n".encode())
                        reply = headers(client)
                        assert reply.split()[1] == b"200", (reply, errors)
                    else:
                        client.sendall(b"\x05\x01\x00")
                        assert exact(client,2) == b"\x05\x00"
                        client.sendall(b"\x05\x01\x00\x03" + bytes([len(DOMAIN)]) + DOMAIN.encode() + b"\x01\xbb")
                        assert exact(client,10)[1] == 0
                    client.sendall(PAYLOAD)
                    assert exact(client,len(PAYLOAD)) == PAYLOAD[::-1]
            with socket.create_connection(("127.0.0.1",local),timeout=15) as c:
                c.sendall(f"CONNECT {blocked}:443 HTTP/1.1\r\nHost: {blocked}:443\r\n\r\n".encode())
                assert headers(c).split()[1] == b"403"
            worker.join(10)
            if errors:
                raise errors[0]
            assert observed == ["TLSv1.3"] * 2, observed
            guest.sh(ctl + "stop")
            assert "state=stopped" in guest.sh(ctl + "status")
            for _ in range(4):
                guest.sh(ctl + "start")
                assert "state=running" in guest.sh(ctl + "status")
                guest.sh(ctl + "stop")
                assert "state=stopped" in guest.sh(ctl + "status")
            print(json.dumps(dict(api=api, abi=abi, zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                application_bytes_each_way=len(PAYLOAD), protocols=["HTTP CONNECT","SOCKS5"], upstream=observed,
                lifecycle_cycles=5, idempotent_apply=True, invalid_apply_retained=True, packaged_block_rule=True)))
        finally:
            try:
                guest.sh(ctl + "stop")
            finally:
                guest.adb("forward","--remove",f"tcp:{local}")
                guest.adb("reverse","--remove","tcp:19443")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("busybox",type=Path)
    args = parser.parse_args()
    run(args.archive, args.busybox)
