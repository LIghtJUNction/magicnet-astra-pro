#!/bin/sh
# Build the foreground TUN adapter and its statically linked dependencies.
set -eu
case ${1:-} in
    linux|android) platform=$1 ;;
    *) echo "usage: $0 linux|android" >&2; exit 2 ;;
esac
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/build/tun"
src="$build/jni"
patch="$root/scripts/tun/android-device.patch"
revision=$(cat "$root/tun.lock")
if ! printf '%s\n' "$revision" | grep -Eq '^[0-9a-f]{40}$'; then
    echo 'Invalid tun.lock' >&2; exit 1
fi
if [ ! -d "$src/.git" ]; then
    mkdir -p "$src"
    git -C "$src" init -q
fi
if ! git -C "$src" cat-file -e "$revision^{commit}" 2>/dev/null; then
    git -C "$src" fetch --depth=1 https://github.com/heiher/hev-socks5-tunnel.git "$revision"
fi
git -C "$src" checkout --detach --quiet "$revision"
git -C "$src" submodule update --init --recursive --depth=1
if ! git -C "$src" apply --reverse --check "$patch" 2>/dev/null; then
    git -C "$src" apply "$patch"
fi
case $platform in
    linux) make -C "$src" -j"${JOBS:-4}" ;;
    android)
        ndk=${ANDROID_NDK_HOME:-${ANDROID_NDK_LATEST_HOME:-}}
        "${ndk:?set ANDROID_NDK_HOME to the Android NDK}/ndk-build" -C "$build" \
            APP_MODULES=hev-socks5-tunnel-bin APP_ABI='arm64-v8a x86_64' \
            APP_PLATFORM=android-23 -j"${JOBS:-4}"
        ;;
esac
