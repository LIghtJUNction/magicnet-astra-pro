"""Create two tiny, debuggable socket clients for disposable Android emulators."""
from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile


def start_selected_activity(guest, uid):
    component = "org.magicnet.trafficfixture.selected/android.app.Activity"
    previous = guest.sh(f"am get-uid-state {uid}")
    launched = guest.sh(f"am start -W -n {component}")
    for _ in range(25):
        state = guest.sh(f"am get-uid-state {uid}")
        if state == "2 (TOP)":
            print(f"Foreground fixture UID {uid}: {previous} -> {state}", flush=True)
            return
        time.sleep(0.2)
    raise RuntimeError(f"UID {uid} did not enter TOP: {previous} -> {state}\n{launched}")


@contextmanager
def installed_clients(guest, probe, *, selected_activity=False):
    # The INTERNET permission and allocated app UID must exist in PackageManager
    # so Android's socket permission checks see the same identity as real apps.
    sdk = Path(os.environ["ANDROID_HOME"])
    versions = sorted((p for p in (sdk / "build-tools").iterdir()
                       if all(s.isdecimal() for s in p.name.split("."))),
                      key=lambda p: tuple(map(int, p.name.split("."))))
    tools = versions[-1]
    platforms = [p for p in (sdk / "platforms").glob("android-*/android.jar")
                 if p.parent.name[8:].isdigit()]
    platform = max(platforms, key=lambda p: int(p.parent.name[8:]))
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as cleanup:
        directory = Path(tmp)
        key = directory / "test.p12"
        subprocess.run(["keytool", "-genkeypair", "-alias", "fixture", "-keyalg", "RSA",
                        "-keystore", key, "-storepass", "fixture", "-keypass", "fixture",
                        "-dname", "CN=Disposable MagicNet fixture", "-validity", "2"],
                       check=True, capture_output=True)
        clients = []
        for name in ("selected", "other"):
            package = "org.magicnet.trafficfixture." + name
            manifest = directory / "AndroidManifest.xml"
            activity = ('<activity android:name="android.app.Activity" android:exported="true" '
                        'android:showWhenLocked="true" android:turnScreenOn="true"/>'
                        if selected_activity and name == "selected" else "")
            manifest.write_text(f'''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
                    package="{package}" android:versionCode="1" android:versionName="1">
                <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35"/>
                <uses-permission android:name="android.permission.INTERNET"/>
                <application android:debuggable="true" android:hasCode="false" android:extractNativeLibs="true">
                    {activity}
                </application>
            </manifest>''')
            unsigned = directory / (name + "-unsigned.apk")
            signed = directory / (name + ".apk")
            subprocess.run([tools / "aapt2", "link", "-I", platform, "--manifest", manifest,
                            "-o", unsigned], check=True)
            with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(probe, "lib/x86_64/librouteprobe.so")
            subprocess.run([tools / "apksigner", "sign", "--ks", key, "--ks-pass", "pass:fixture",
                            "--out", signed, unsigned], check=True)
            assert not guest.sh(f"pm list packages {package}"), f"fixture already exists: {package}"
            guest.adb("install", str(signed))
            cleanup.callback(guest.adb, "uninstall", package)
            uid = int(guest.sh(f"run-as {package} id -u"))
            assert uid % 100000 >= 10000
            installed = guest.sh(f"pm path {package}").removeprefix("package:")
            executable = str(Path(installed).parent / "lib/x86_64/librouteprobe.so")
            clients.append((uid, f"run-as {package} {guest.quote(executable)} --client {uid}"))
        yield clients
