import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
import os

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"src/magicnet-astra-pro/lib/patch.sh"


class Delta(unittest.TestCase):
    def test_reuse_and_atomic_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            core=os.urandom(100000)
            for name,ui in (("old",b"v1"),("new",b"v2")):
                with zipfile.ZipFile(p/name,"w",zipfile.ZIP_DEFLATED) as z:
                    z.writestr("bin/magicbox",core)
                    z.writestr("webroot/app.js",ui)
            subprocess.run(["python3",ROOT/"scripts/delta.py",p/"old",p/"new",p/"delta"],check=True)
            sha=hashlib.sha256((p/"new").read_bytes()).hexdigest()
            def apply(expected):
                return subprocess.run(["sh","-c",'. "$1"; shift; apply_patch_zip "$@"', "sh",PATCH,
                                       p/"old",p/"delta",p/"result",expected]).returncode
            self.assertLess((p/"delta").stat().st_size,2000)
            self.assertEqual(apply(sha),0)
            self.assertEqual((p/"result").read_bytes(),(p/"new").read_bytes())
            (p/"result").write_bytes(b"prior")
            self.assertNotEqual(apply("0"*64),0)
            with zipfile.ZipFile(p/"delta","w") as z:
                z.writestr("index","truncated\n")
            self.assertNotEqual(apply(sha),0)
            self.assertEqual((p/"result").read_bytes(), b"prior")


if __name__=="__main__":
    unittest.main()
