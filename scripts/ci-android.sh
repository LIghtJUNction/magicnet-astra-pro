#!/bin/sh
set -eu
# android-emulator-runner starts one disposable AVD.
ANDROID_SERIAL=$(adb devices | awk '$1 ~ /^emulator-/ && $2 == "device" {print $1}')
export ANDROID_SERIAL
case $ANDROID_SERIAL in emulator-[0-9]*) ;; *) echo 'Exactly one emulator is required.' >&2; exit 1;; esac
is_virtual=$(adb shell 'getprop ro.kernel.qemu; getprop ro.boot.qemu' | tr -d '\r')
printf '%s\n' "$is_virtual" | grep -Fxq 1
tools="$RUNNER_TEMP/magicnet-tools"
adb root
adb wait-for-device
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
