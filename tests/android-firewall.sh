#!/bin/sh
# Host harness. Explicitly refuse a physical device.
set -eu
: "${ANDROID_SERIAL:?set ANDROID_SERIAL to the emulator serial}"
case $ANDROID_SERIAL in emulator-[0-9]*) ;; *) echo 'An emulator serial is required.' >&2; exit 1;; esac
is_virtual=$(adb shell 'getprop ro.kernel.qemu; getprop ro.boot.qemu' | tr -d '\r')
printf '%s\n' "$is_virtual" | grep -Fxq 1 || { echo 'Emulator required.' >&2; exit 1; }
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
adb push "$here/firewall-device.sh" /data/local/tmp/mna-firewall-test.sh >/dev/null
# API 23 adb shell may lose the remote exit code; require the verifier receipt.
output=$(adb shell sh /data/local/tmp/mna-firewall-test.sh)
printf '%s\n' "$output"
printf '%s\n' "$output" | tr -d '\r' | grep -Fxq 'MNA_FIREWALL_TEST_OK'
