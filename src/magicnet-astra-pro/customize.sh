# Each release archive contains one Android ABI.
set_perm "$MODPATH/cli" 0 0 0755
set_perm "$MODPATH/bin/magicbox" 0 0 0755
set_perm "$MODPATH/bin/magicbox-dns-guard" 0 0 0755
MAGICBOX_BLOCKLIST="$MODPATH/rules/block.txt" "$MODPATH/bin/magicbox" check "$MODPATH/default.toml" >/dev/null ||
    abort 'Magicbox cannot execute on this device. Check the ZIP architecture.'
