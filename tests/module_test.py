"""Linux lifecycle and configuration tests running the real module CLI and core."""
import base64
import ssl
import concurrent.futures
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "src/magicnet-astra-pro"
BINARY = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else None
RULES = "magicbox-exact-v1\nblocked.example\n"


class Module(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name, "module")
        self.state = Path(work.name, "state")
        self.env = {**os.environ, "MAGICNET_STATE_DIR": str(self.state)}
        shutil.copytree(MODULE, self.root)
        (self.root / "bin").mkdir(exist_ok=True)
        shutil.copyfile(BINARY, self.root / "bin/magicbox")
        (self.root / "bin/magicbox").chmod(0o755)
        (self.root / "rules").mkdir(exist_ok=True)
        (self.root / "rules/block.txt").write_text(RULES)
        self.addCleanup(lambda: self.cli("stop", success=None))

    def cli(self, *args, data=None, env=None, success=True):
        result = subprocess.run(
            ["sh", str(self.root / "cli"), *args], env=env or self.env, input=data,
            capture_output=True, text=True, timeout=15,
        )
        if success is not None:
            self.assertEqual(result.returncode == 0, success, result.stderr + result.stdout)
        return result

    def test_first_run_and_rollback_on_rejection(self):
        self.assertIn("state=stopped", self.cli("status").stdout)
        self.assertIn("no_upstream", self.cli("start", success=False).stderr)
        self.cli("boot")
        valid = "socks5://user:p%40ss@127.0.0.1:17011"
        web = {**self.env, "MAGICNET_INPUT_B64": base64.b64encode(valid.encode()).decode()}
        self.cli("web-configure", env=web)
        self.assertIn(valid, (self.state / "config.toml").read_text())
        self.assertEqual((self.state / "config.toml").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("user", self.cli("show").stdout)
        self.assertNotIn("p%40ss", self.cli("status").stdout)

        invalid = ["socks5://127.0.0.1:1080", "socks5://name.example:1080",
                   'http://127.0.0.1:80"\ninvalid = "true']
        for endpoint in invalid:
            self.cli("configure", endpoint, success=False)
            self.assertIn(valid, (self.state / "config.toml").read_text())

        (self.root / "rules/block.txt").unlink()
        self.cli("start", success=False)
        self.assertFalse((self.state / "enabled").exists())
        self.assertEqual(list(self.state.glob(".edit.*")), [])

    def test_shadowsocks_share_link_is_validated_and_redacted(self):
        blob = base64.urlsafe_b64encode(b"aes-128-gcm:test-secret").decode().rstrip("=")
        self.cli("configure", f"ss://{blob}@192.0.2.9:8388#Office")
        self.assertIn("upstream=ss://192.0.2.9:8388", self.cli("status").stdout)
        self.assertNotIn(blob, self.cli("status").stdout)
        rejection = self.cli("configure", "ss://aes-128-cfb:obsolete@192.0.2.1:8388", success=False)
        self.assertNotIn("obsolete", rejection.stderr)
        self.assertIn("upstream=ss://192.0.2.9:8388", self.cli("status").stdout)

    def test_start_reload_boot_stop(self):
        first = "http://127.0.0.1:17012"
        self.cli("configure", first)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as calls:
            list(calls.map(lambda _: self.cli("start"), range(4)))
        pid = (self.state / "pid").read_text()
        with socket.create_connection(("127.0.0.1", 1080), timeout=2) as client:
            client.sendall(bytes([5, 1, 0]))
            self.assertEqual(client.recv(2), bytes([5, 0]))
        self.assertIn("state=running", self.cli("status").stdout)
        self.cli("configure", first)
        self.assertEqual(pid, (self.state / "pid").read_text())
        self.cli("configure", "socks5://127.0.0.1:17013")
        self.assertNotEqual(pid, (self.state / "pid").read_text())
        self.assertIn("state=running", self.cli("status").stdout)
        self.cli("stop")
        self.cli("boot")
        self.assertIn("state=stopped", self.cli("status").stdout)
        (self.state / "enabled").touch()
        self.cli("boot")
        self.assertIn("state=running", self.cli("status").stdout)
        self.cli("uninstall")
        self.assertFalse((self.state / "config.toml").exists())

    def test_stale_pid_never_signalled(self):
        self.state.mkdir()
        with subprocess.Popen(["sleep", "20"]) as foreign:
            try:
                stat = Path(f"/proc/{foreign.pid}/stat").read_text().split(") ", 1)[1].split()
                (self.state / "pid").write_text(f"{foreign.pid} {stat[19]}\n")
                self.cli("stop")
                self.assertIsNone(foreign.poll())
            finally:
                foreign.terminate()

    def test_file_and_web_import_with_same_index(self):
        raw = "http://127.0.0.1:17012\nsocks5://127.0.0.1:17013\n"
        self.cli("import", "-", "2", data=raw)
        self.assertIn("socks5://127.0.0.1:17013", self.cli("status").stdout)
        web = {**self.env, "MAGICNET_INPUT_B64": base64.b64encode(raw.encode()).decode()}
        listing = self.cli("web-preview-file", env=web).stdout
        token = listing.splitlines()[0].removeprefix("preview=")
        self.assertRegex(token, r"^[a-f0-9]{24}$")
        self.assertNotIn("127.0.0.1", listing)
        self.assertIn("2\tsocks5\tready", listing)
        second = self.cli("web-preview-file", env=web).stdout.splitlines()[0].removeprefix("preview=")
        self.cli("web-apply", token, "1", success=False)
        self.cli("web-apply", second, "1")
        self.assertFalse(list(self.state.glob("preview-feed.*")))
        self.assertIn("http://127.0.0.1:17012", self.cli("status").stdout)
        self.cli("import", "-", "999", data=raw, success=False)
        self.assertIn("http://127.0.0.1:17012", self.cli("status").stdout)
        self.cli("import", "-", "1", data="age-encryption.org/v1\n", success=False)
        self.assertIn("proxy_required", self.cli("fetch", "https://unknown.invalid/feed", success=False).stderr)

    @unittest.skipUnless(shutil.which("curl") and shutil.which("openssl"), "curl and openssl required")
    def test_real_subscription_https_through_socks5(self):
        self.state.mkdir()
        key, cert = self.state / "test.key", self.state / "test.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=subscriptions.invalid", "-addext", "subjectAltName=DNS:subscriptions.invalid",
                        "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        observations = []

        def exact(sock, count):
            data = b""
            while len(data) < count:
                chunk = sock.recv(count - len(data))
                if not chunk:
                    raise EOFError("premature upstream close")
                data += chunk
            return data

        with socket.socket() as upstream:
            upstream.bind(("127.0.0.1", 0))
            upstream.listen()
            upstream.settimeout(6)

            def serve():
                peer, _ = upstream.accept()
                with peer:
                    peer.settimeout(6)
                    greeting = exact(peer, 2)
                    self.assertIn(0, exact(peer, greeting[1]))
                    peer.sendall(bytes([5, 0]))
                    # The .invalid name must reach the upstream as a domain.
                    self.assertEqual(exact(peer, 4), bytes([5, 1, 0, 3]))
                    name = exact(peer, exact(peer, 1)[0])
                    self.assertEqual(name, b"subscriptions.invalid")
                    self.assertEqual(int.from_bytes(exact(peer, 2), "big"), 443)
                    peer.sendall(bytes([5, 0, 0, 1, 127, 0, 0, 1, 0, 0]))
                    with tls.wrap_socket(peer, server_side=True) as secure:
                        headers = b""
                        while b"\r\n\r\n" not in headers:
                            headers += exact(secure, 1)
                            self.assertLess(len(headers), 16384)
                        observations.append(headers)
                        body = b"http://127.0.0.1:17019\n"
                        secure.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: " +
                                       str(len(body)).encode() + b"\r\n\r\n" + body)

            self.cli("configure", f"socks5://127.0.0.1:{upstream.getsockname()[1]}")
            self.cli("start")
            env = {**self.env, "NO_PROXY": "*", "CURL_CA_BUNDLE": str(cert)}
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                serving = pool.submit(serve)
                self.cli("fetch", "https://subscriptions.invalid/feed?key=temporary", "Mobile/Test", env=env)
                serving.result(timeout=8)
        self.assertIn(b"GET /feed?key=temporary HTTP/1.1", observations[0])
        self.assertIn(b"User-Agent: Mobile/Test", observations[0])
        self.assertIn("http://127.0.0.1:17019", self.cli("status").stdout)
        self.assertIn("state=running", self.cli("status").stdout)

    @unittest.skipUnless(shutil.which("age") and shutil.which("age-keygen"), "age tools required")
    def test_real_age_binary_and_armored_feeds(self):
        self.state.mkdir()
        identity = self.state / "identity.txt"
        subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
        public = subprocess.check_output(["age-keygen", "-y", str(identity)], text=True).strip()
        for extra in ([], ["--armor"]):
            ciphertext = subprocess.check_output(["age", *extra, "-r", public],
                                                 input=b"http://127.0.0.1:17021\n")
            feed = self.state / "nodes.age"
            feed.write_bytes(ciphertext)
            self.cli("import", str(feed))
            self.assertIn("http://127.0.0.1:17021", self.cli("status").stdout)
            other = self.state / "other-identity"
            if not other.exists():
                subprocess.run(["age-keygen", "-o", str(other)], check=True, capture_output=True)
            env = {**self.env, "MAGICNET_AGE_IDENTITY": str(other)}
            self.assertIn("decrypt_failed", self.cli("import", str(feed), env=env, success=False).stderr)
            self.assertIn("http://127.0.0.1:17021", self.cli("status").stdout)

    def test_https_subscription_options_and_failure_retention(self):
        self.cli("configure", "http://127.0.0.1:17012")
        self.cli("start")
        # Inspect transport flags without making an external request.
        tool = self.state / "curl"
        tool.write_text("""#!/bin/sh
printf '%s\\n' "$@" > "$MAGICNET_STATE_DIR/curl-args"
cat > "$MAGICNET_STATE_DIR/curl-config"
while [ "$#" -gt 0 ]; do
    if [ "$1" = --output ]; then printf 'http://127.0.0.1:17018\\n' > "$2"; fi
    shift
done
""")
        tool.chmod(0o755)
        env = {**self.env, "PATH": str(self.state) + ":" + os.environ["PATH"], "NO_PROXY": "*"}
        url = "https://unknown.invalid/feed?private=test"
        self.cli("fetch", url, "My Client/1", env=env)
        flags = (self.state / "curl-args").read_text().splitlines()
        self.assertNotIn(url, flags)
        self.assertEqual(flags[flags.index("--noproxy") + 1], "")
        self.assertEqual(flags[flags.index("--proxy") + 1], "socks5h://127.0.0.1:1080")
        for option in ["--proto", "--proto-redir"]:
            self.assertEqual(flags[flags.index(option) + 1], "=https")
        self.assertIn('user-agent = "My Client/1"', (self.state / "curl-config").read_text())
        self.assertIn("http://127.0.0.1:17018", self.cli("status").stdout)
        tool.write_text("#!/bin/sh\nexit 1\n")
        self.cli("fetch", url, env=env, success=False)
        self.assertIn("http://127.0.0.1:17018", self.cli("status").stdout)
        self.assertEqual(list(self.state.glob(".edit.*")), [])


if __name__ == "__main__":
    if BINARY is None or not BINARY.is_file():
        sys.exit("usage: python3 tests/module_test.py /path/to/magicbox")
    unittest.main(verbosity=2)
