"""ADB test helper restricted to disposable Android emulator images."""
import os
import secrets
import shlex
import subprocess


class Guest:
    quote = staticmethod(shlex.quote)

    def __init__(self):
        self.path = "/data/local/tmp/magicnet-test-" + secrets.token_hex(8)
        if not os.getenv("ANDROID_SERIAL"):
            raise RuntimeError("select a disposable AVD using ANDROID_SERIAL")

    def adb(self, *args):
        return subprocess.run(["adb", "-s", os.environ["ANDROID_SERIAL"], *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180).stdout.decode().replace("\r","")

    def sh(self, command, success=True):
        # Android 6 shell transport can report zero even when the guest failed.
        marker = "__mna_" + secrets.token_hex(12)
        output = self.adb("shell", f"( {command} ); rc=$?; printf '\\n{marker}=%s\\n' \"$rc\"")
        body, sep, code = output.rpartition("\n" + marker + "=")
        if not sep or ((code.strip() == "0") != success):
            raise RuntimeError(output)
        return body.strip()

    def __enter__(self):
        if self.adb("shell", "getprop ro.kernel.qemu").strip() != "1" and self.adb("shell", "getprop ro.boot.qemu").strip() != "1":
            raise RuntimeError("expected an Android emulator")
        self.sh(f"mkdir -m 700 {self.path}")
        return self

    def __exit__(self, *exc):
        self.sh(f"rm -rf {self.path}")
