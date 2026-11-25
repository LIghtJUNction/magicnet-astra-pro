import hashlib
from pathlib import Path
import tempfile
import unittest

from build import fetch, parse_exact, write_changed
from catalog import optimize


class RuleTests(unittest.TestCase):
    def test_dns_normalization_and_sentinels(self):
        self.assertEqual(parse_exact(b"# test\nZ.example.\na.test\nz.EXAMPLE\n"),
                         (["a.test", "z.example"], 3))
        for bad in [b"*.test", b"a..test", b"foo\x00.bar", b"x.-test", b"GITHUB.COM.", b"# empty"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_exact(bad)

    def test_group_distinct_syntax_and_singletons(self):
        source = [
            {"version": 1, "rules": [{"domain_suffix": ".test", "domain_regex": "^a\\.x$"}]},
            {"version": 2, "rules": [{"domain": ["x", "x"], "domain_suffix": [".test", "test"]}]},
        ]
        sets, before, after = optimize(source)
        self.assertEqual((before, after), (6, 5))
        self.assertEqual(sets[0]["rules"][0]["domain_regex"], ["^a\\.x$"])
        self.assertEqual(sets[1]["rules"][0]["domain_suffix"], [".test", "test"])
        self.assertEqual(sets[1]["rules"][0]["domain"], ["x"])

    def test_ip_union_preserves_exact_address_membership(self):
        v = {"version": 2, "rules": [{"ip_cidr": ["192.0.2.0/25", "192.0.2.128/25", "::1/128"]}]}
        out, _, count = optimize([v])
        self.assertEqual(out[0]["rules"][0]["ip_cidr"], ["192.0.2.0/24", "::1/128"])
        self.assertEqual(count, 2)
        for unknown in [{"invert": True, "domain": ["test"]}, {"source_ip_cidr": ["192.0.2.0/24"]}]:
            with self.subTest(unknown=unknown), self.assertRaises(ValueError):
                optimize([{"version": 2, "rules": [unknown]}])

    def test_changed_objects_and_digest_verification(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            write_changed(path, {"a": b"a", "b": b"b"})
            old = (path / "a").stat()
            write_changed(path, {"a": b"a", "b": b"c"})
            self.assertEqual((path / "a").stat().st_ino, old.st_ino)
            self.assertEqual((path / "a").stat().st_mtime_ns, old.st_mtime_ns)
            self.assertEqual((path / "b").read_bytes(), b"c")
            pin = {"url": "example", "sha256": hashlib.sha256(b"a").hexdigest()}
            self.assertEqual(fetch(pin, path / "a"), b"a")
            with self.assertRaises(ValueError):
                fetch(pin, path / "b")
