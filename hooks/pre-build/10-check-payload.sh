#!/bin/sh
set -eu
: "${KAM_MODULE_ROOT:?run this hook with kam build}"
[ -x "$KAM_MODULE_ROOT/bin/magicbox" ] || { echo 'Stage the Android magicbox binary in bin/magicbox before building.' >&2; exit 1; }
[ -s "$KAM_MODULE_ROOT/rules/block.txt" ] || { echo 'Build the default rules before packaging.' >&2; exit 1; }
[ -x "$KAM_MODULE_ROOT/bin/magicbox-dns-guard" ] || { echo "Stage the Android DNS guard before building." >&2; exit 1; }
[ -x "$KAM_MODULE_ROOT/bin/hev-socks5-tunnel" ] || { echo 'Build the Android TUN adapter before packaging.' >&2; exit 1; }
