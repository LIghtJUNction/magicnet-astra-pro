#!/bin/sh
set -eu
# android-emulator-runner starts one disposable AVD.
ANDROID_SERIAL=$(adb devices | awk '$1 ~ /^emulator-/ && $2 == "device" {print $1}')
export ANDROID_SERIAL
case $ANDROID_SERIAL in emulator-[0-9]*) ;; *) echo 'Exactly one emulator is required.' >&2; exit 1;; esac
is_virtual=$(adb shell 'getprop ro.kernel.qemu; getprop ro.boot.qemu' | tr -d '\r')
printf '%s\n' "$is_virtual" | grep -Fxq 1
tools="$RUNNER_TEMP/magicnet-tools"
# adbd can close its transport before the host receives the root reply.
for attempt in 1 2 3; do
    if [ "$(timeout 8 adb shell id -u | tr -d '\r')" = 0 ]; then
        break
    fi
    timeout 10 adb root || true
    timeout 15 adb wait-for-device || true
    sleep 1
done
if [ "$(timeout 8 adb shell id -u | tr -d '\r')" != 0 ]; then
    echo "Unable to obtain UID 0 on $ANDROID_SERIAL after three attempts." >&2
    exit 1
fi
adb push "$tools/kam" /data/local/tmp/kam
adb shell chmod 755 /data/local/tmp/kam
if [ "$1" = package ]; then
    mkdir -p dist
    for pair in 'aarch64-linux-android arm64-v8a' 'x86_64-linux-android x86_64'; do
        set -- $pair
        python3 scripts/package.py --binary "core/target/$1/release/magicbox" --abi "$2" --rules build/rules \
            --emulator-kam /data/local/tmp/kam --out "dist/magicnet-$2.zip"
    done
fi
python3 tests/android_tunnels.py dist/magicnet-x86_64.zip "$tools/busybox"
adb push "$tools/busybox" /data/local/tmp/busybox
adb push dist/magicnet-x86_64.zip /data/local/tmp/module.zip
adb shell 'chmod 755 /data/local/tmp/busybox && mkdir -p /data/local/tmp/mna-install && cd /data/local/tmp/mna-install && /data/local/tmp/busybox unzip -oq /data/local/tmp/module.zip'
sh tests/android-firewall.sh

ndk="$ANDROID_NDK_LATEST_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
"$ndk/x86_64-linux-android23-clang" -Os -Wall -Wextra -Werror tests/udp-probe.c -o "$RUNNER_TEMP/magicnet-udp-probe"
python3 tests/android_udp.py /data/local/tmp/mna-install/bin/magicbox "$RUNNER_TEMP/magicnet-udp-probe"
"$ndk/x86_64-linux-android23-clang" -Os -Wall -Wextra -Werror tests/route-probe.c -o "$RUNNER_TEMP/magicnet-route-probe"
python3 tests/android_traffic.py /data/local/tmp/mna-install "$RUNNER_TEMP/magicnet-route-probe"
python3 tests/android_tun_default.py --serial "$ANDROID_SERIAL" --archive dist/magicnet-x86_64.zip \
    --busybox "$tools/busybox" --probe "$RUNNER_TEMP/magicnet-route-probe"
