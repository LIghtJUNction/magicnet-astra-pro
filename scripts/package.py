"""Build and verify a single-ABI KAM module."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = "magicnet-astra-pro"
ARCH = {"arm64-v8a": 183, "x86_64": 62}


def check_elf(blob, abi):
    if blob[:6] != b"\x7fELF\x02\x01" or len(blob) < 64 or struct.unpack_from("<H", blob, 18)[0] != ARCH[abi]:
        raise ValueError(f"expected a 64-bit little-endian {abi} ELF")
    if b"/system/bin/linker64\0" not in blob:
        raise ValueError("expected Android dynamic linker")


def stage(destination, binary, rules, abi, for_android=False):
    target = destination / "src" / MODULE
    shutil.copytree(ROOT / "src" / MODULE, target, ignore=shutil.ignore_patterns("bin", "rules"))
    shutil.copytree(ROOT / "hooks", destination / "hooks")
    shutil.copy2(ROOT / "kam.toml", destination)
    metadata = tomllib.loads((destination / "kam.toml").read_text())["prop"]
    prop = dict(line.split("=", 1) for line in (target / "module.prop").read_text().splitlines() if "=" in line)
    for key in ("id", "name", "version", "versionCode", "author", "description"):
        if prop.get(key) != str(metadata[key]):
            raise ValueError(f"module.prop mismatch in {key}")
    if for_android:
        hook = destination / "hooks/pre-build/10-check-payload.sh"
        head, body = hook.read_bytes().split(b"\n", 1)
        if head != b"#!/bin/sh":
            raise ValueError("unrecognized hook interpreter")
        hook.write_bytes(b"#!/system/bin/sh\n" + body)
    (target / "bin").mkdir()
    tun = ROOT / "build/tun"
    for name, path in (
        ("magicbox", binary),
        ("magicbox-dns-guard", binary.with_name("magicbox-dns-guard")),
        ("hev-socks5-tunnel", tun / "libs" / abi / "hev-socks5-tunnel-bin"),
    ):
        data = path.read_bytes()
        check_elf(data, abi)
        executable = target / "bin" / name
        executable.write_bytes(data)
        executable.chmod(0o755)
    (target / "rules").mkdir()
    for name in ("block.txt", "NOTICE.txt", "COPYING.HaGeZi"):
        shutil.copy2(rules / name, target / "rules" / name)
    licenses = target / "licenses"
    licenses.mkdir()
    for component, subdir in (
        ("hev-socks5-tunnel", "."), ("hev-socks5-core", "src/core"),
        ("hev-task-system", "third-part/hev-task-system"),
        ("lwip", "third-part/lwip"), ("yaml", "third-part/yaml"),
    ):
        shutil.copyfile(tun / "jni" / subdir / "LICENSE", licenses / component)
    shutil.copyfile(ROOT / "scripts/tun/COPYING.libyaml", licenses / "libyaml")
    # lwIP also carries file-specific BSD notices with additional contributors.
    notices = set()
    for path in (tun / "jni/third-part/lwip/src").rglob("*"):
        if path.suffix in (".c", ".h"):
            for block in re.findall(rb"/\*.*?\*/", path.read_bytes(), re.S):
                if b"copyright" in block.lower():
                    notices.add(block.replace(b"\r\n", b"\n"))
    (licenses / "lwip-source-notices").write_bytes(b"\n\n".join(sorted(notices)) + b"\n")
    shutil.copy2(ROOT / "LICENSE", target / "LICENSE")
    return target


def verify(archive, source):
    expected = {p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()}
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != expected.keys():
            raise ValueError(f"ZIP and staged module disagree: {set(names) ^ expected.keys()}")
        for name, path in expected.items():
            if hashlib.sha256(z.read(name)).digest() != hashlib.sha256(path.read_bytes()).digest():
                raise ValueError(f"archive member mismatch: {name}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--rules", type=Path, required=True)
    p.add_argument("--abi", choices=ARCH, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--emulator-kam", help="path to KAM inside an Android emulator selected by ADB")
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        source = stage(work, args.binary, args.rules, args.abi, bool(args.emulator_kam))
        archive = work / "dist" / f"{MODULE}.zip"
        if args.emulator_kam:
            import sys
            sys.path.insert(0, str(ROOT / "tests"))
            from android_guest import Guest
            with Guest() as guest:
                guest.adb("push", str(work) + "/.", guest.path + "/")
                guest.sh(f'cd {guest.path} && export HOME={guest.path} && chmod 755 hooks/pre-build/*.sh src/{MODULE}/bin/magicbox && {guest.quote(args.emulator_kam)} build -q')
                archive.parent.mkdir(exist_ok=True)
                guest.adb("pull", f"{guest.path}/dist/{archive.name}", str(archive))
        else:
            subprocess.run(["kam", "build"], cwd=work, check=True)
        verify(archive, source)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=args.out.parent, delete=False) as f:
            tmp = Path(f.name)
        try:
            shutil.copyfile(archive, tmp)
            os.replace(tmp, args.out)
        finally:
            tmp.unlink(missing_ok=True)
        print(f"{args.out.name} {args.out.stat().st_size} bytes {hashlib.sha256(args.out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
