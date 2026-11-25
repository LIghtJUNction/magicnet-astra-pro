"""Create a verified byte delta between two KAM ZIPs, including rebuilt ZIPs."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import zipfile

MAX = 64 * 1024 * 1024


def read(archive):
    if archive.stat().st_size > MAX:
        raise ValueError("module ZIP exceeds 64 MiB")
    data = archive.read_bytes()
    with zipfile.ZipFile(archive) as z:
        records = z.infolist()
        if len(records) > 1024:
            raise ValueError("too many ZIP members")
        starts = {0, z.start_dir, len(data)}
        for entry in records:
            header = entry.header_offset
            if data[header:header + 4] != b"PK\x03\x04" or header + 30 > z.start_dir:
                raise ValueError("invalid local ZIP header")
            name_len, extra_len = struct.unpack_from("<HH", data, header + 26)
            payload = header + 30 + name_len + extra_len
            end = payload + entry.compress_size
            if end > z.start_dir:
                raise ValueError("invalid compressed member size")
            # DOS timestamps and extra fields can change while the complete
            # compressed payload remains byte-identical, even after reordering.
            starts.update((header, payload, end))
    points = sorted(starts)
    return data, list(zip(points, points[1:]))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make(old, new, dest):
    before, old_spans = read(old)
    after, new_spans = read(new)
    existing = {digest(before[a:b]): a for a, b in old_spans}
    operations = []
    for a, b in new_spans:
        source = existing.get(digest(after[a:b]))
        kind, start = ("part", a) if source is None else ("copy", source)
        if operations and operations[-1][0] == kind and operations[-1][1] + operations[-1][2] == start:
            last_kind, offset, length = operations.pop()
            operations.append((last_kind, offset, length + b - a))
        else:
            operations.append((kind, start, b - a))
    if len(operations) > 1024:
        raise ValueError("delta exceeds shell operation limit")
    lines = [f"magicnet-delta-v1 {digest(before)} {digest(after)} {len(after)}"]
    reused = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as out:
        path = Path(out.name)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
            for i, (kind, offset, length) in enumerate(operations):
                if kind == "copy":
                    reused += length
                    lines.append(f"copy {offset} {length}")
                else:
                    z.writestr(f"part-{i}", after[offset:offset + length])
                    lines.append(f"part {i} {length}")
            z.writestr("index", "\n".join(lines) + "\n")
        os.replace(path, dest)
    finally:
        path.unlink(missing_ok=True)
    print(f"reused={reused} target={len(after)} delta={dest.stat().st_size} sha256={digest(after)}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("old", "new", "delta"):
        cli.add_argument(name, type=Path)
    args = cli.parse_args()
    make(args.old, args.new, args.delta)
