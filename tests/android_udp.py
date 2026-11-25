"""Run the packaged UDP relay on Android with a host-side SOCKS5 peer."""
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from android_guest import Guest


def exact(sock, count):
    data = bytearray()
    while len(data) < count:
        block = sock.recv(count - len(data))
        if not block:
            raise EOFError("unexpected control EOF")
        data.extend(block)
    return bytes(data)


def peer(listener, udp_port):
    control, _ = listener.accept()
    with control:
        control.settimeout(30)
        assert exact(control, 3) == b"\x05\x01\x00"
        control.sendall(b"\x05\x00")
        assert exact(control, 10) == b"\x05\x03\x00\x01" + bytes(6)
        control.sendall(b"\x05\x00\x00\x01" + bytes(4) + struct.pack("!H", udp_port))
        assert control.recv(1) == b""


def main(binary, probe):
    with Guest() as g, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.settimeout(40)
        listener.listen(1)
        g.adb("push", str(Path(probe).resolve()), g.path + "/probe")
        g.sh(f"chmod 755 {g.path}/probe")
        g.sh(f"cd {g.path}; ./probe --echo </dev/null >udp-port 2>error & echo $! >echo-pid")
        udp_port = int(g.sh(f"cat {g.path}/udp-port"))
        upstream = 19432
        g.adb("reverse", f"tcp:{upstream}", f"tcp:{listener.getsockname()[1]}")
        config = f'listen = "127.0.0.1:0"\nupstream = "socks5://127.0.0.1:{upstream}"\n'
        g.sh(f"printf %s {g.quote(config)} > {g.path}/config")
        g.sh(f"cd {g.path}; {g.quote(binary)} run config </dev/null >ready 2>&1 & echo $! >pid")
        forward = None
        try:
            for _ in range(40):
                status = g.sh(f"cat {g.path}/ready")
                if status.startswith("ready 127.0.0.1:"):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Android proxy did not listen: " + status)
            port = int(status.partition("127.0.0.1:")[2].split()[0])
            forward = int(g.adb("forward", "tcp:0", f"tcp:{port}"))
            with ThreadPoolExecutor(max_workers=1) as executor:
                reference = executor.submit(peer, listener, udp_port)
                with socket.create_connection(("127.0.0.1", forward), timeout=20) as app:
                    app.sendall(b"\x05\x01\x00")
                    assert exact(app, 2) == b"\x05\x00"
                    app.sendall(b"\x05\x03\x00\x01" + bytes(6))
                    assert exact(app, 8) == b"\x05\x00\x00\x01\x7f\x00\x00\x01"
                    local = int.from_bytes(exact(app, 2), "big")
                    assert g.sh(f"{g.path}/probe {local}") == "ANDROID_UDP_ECHO_OK"
                reference.result()
        finally:
            if forward is not None:
                g.adb("forward", "--remove", f"tcp:{forward}")
            g.adb("reverse", "--remove", f"tcp:{upstream}")
            g.sh(f"kill $(cat {g.path}/pid) $(cat {g.path}/echo-pid) 2>/dev/null || true")
        print("ANDROID_SOCKS5_UDP_PASS: named destination, two-way datagram and control teardown")


if __name__ == "__main__":
    main(*sys.argv[1:])
