"""Build a delta between two original KAM ZIPs, copying unchanged ZIP records."""
import argparse
import hashlib
from pathlib import Path
import tempfile
import zipfile
import os

MAX = 64 * 1024 * 1024


def read(archive):
    if archive.stat().st_size > MAX:
        raise ValueError("module ZIP exceeds 64 MiB")
    data = archive.read_bytes()
    with zipfile.ZipFile(archive) as z:
        starts = sorted({0, z.start_dir, len(data), *(i.header_offset for i in z.infolist())})
    return data, [(a,b) for a,b in zip(starts, starts[1:]) if b>a]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make(old, new, dest):
    before, old_spans = read(old)
    after, new_spans = read(new)
    existing = {digest(before[a:b]): a for a,b in old_spans}
    if max(len(old_spans),len(new_spans)) > 1024:
        raise ValueError("too many ZIP records")
    lines = [f"magicnet-delta-v1 {digest(before)} {digest(after)} {len(after)}"]
    reused = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as out:
        path = Path(out.name)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
            for i, (a,b) in enumerate(new_spans):
                piece = after[a:b]
                start = existing.get(digest(piece))
                if start is not None:
                    lines.append(f"copy {start} {len(piece)}")
                    reused += len(piece)
                else:
                    z.writestr(f"part-{i}", piece)
                    lines.append(f"part {i} {len(piece)}")
            z.writestr("index", "\n".join(lines)+"\n")
        os.replace(path, dest)
    finally:
        path.unlink(missing_ok=True)
    print(f"reused={reused} target={len(after)} delta={dest.stat().st_size} sha256={digest(after)}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("old","new","delta"):
        cli.add_argument(name,type=Path)
    args = cli.parse_args()
    make(args.old,args.new,args.delta)
