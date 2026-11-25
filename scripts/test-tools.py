"""Fetch digest-pinned Android test tools; none are shipped in a module."""
from pathlib import Path
import hashlib
import io
import os
import urllib.request
import zipfile


def download(url, expected):
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("test tool digest mismatch")
    return data


out = Path(os.environ["RUNNER_TEMP"]) / "magicnet-tools"
out.mkdir(exist_ok=True)
(out / "kam").write_bytes(download(
    "https://github.com/MemDeco-WG/Kam/releases/download/v0.6.16/kam-android-x86_64",
    "befac0ef32fd66c9bdc3eca097b56de65a39cf94de7135a9fa5789805ca43782"))
apk = download("https://github.com/topjohnwu/Magisk/releases/download/v31.1/app-debug.apk",
               "b983c975663feebaaf0bcc63fe57a8c4406914ec2b4a08fa3259bca817a10778")
with zipfile.ZipFile(io.BytesIO(apk)) as z:
    (out / "busybox").write_bytes(z.read("lib/x86_64/libbusybox.so"))
