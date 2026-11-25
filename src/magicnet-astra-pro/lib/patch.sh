# Apply to a new ZIP beside the destination. The caller supplies the expected
# release digest separately from the patch, so a modified patch cannot pass.
apply_patch_zip() (
    set -eu
    [ "$#" = 4 ] || { echo 'usage: magicnet patch OLD DELTA NEW EXPECTED_SHA256' >&2; exit 2; }
    old=$1 delta=$2 dest=$3 expected=$4
    case "$expected" in *[!0-9a-f]*|'') exit 2;; esac
    [ "${#expected}" -eq 64 ] && [ -f "$old" ] && [ -f "$delta" ] || exit 2
    outdir=$(dirname -- "$dest")
    base=$(basename -- "$dest")
    case $base in .|..|/) exit 2;; esac
    [ ! -d "$dest" ] || exit 2
    tmp=$(mktemp -d "$outdir/.magicnet-patch.XXXXXX")
    trap 'rm -rf "$tmp"' EXIT
    trap 'exit 1' INT TERM HUP
    bytes() { wc -c < "$1"; }
    sha() { sha256sum < "$1" | cut -d ' ' -f 1; }
    number() { case $1 in ""|*[!0-9]*|0?*) return 1;; esac; [ "${#1}" -le 8 ]; }
    max=67108864
    oldsize=$(bytes "$old")
    [ "$oldsize" -le "$max" ] && [ "$(bytes "$delta")" -le 68157440 ] || exit 1
    unzip -p "$delta" index | head -c 65537 > "$tmp/index"
    [ "$(bytes "$tmp/index")" -le 65536 ] || exit 1
    exec 3< "$tmp/index"
    read -r format oldhash newhash total extra <&3
    [ "$format" = magicnet-delta-v1 ] && [ -z "$extra" ] && [ "$newhash" = "$expected" ] &&
        [ "$oldhash" = "$(sha "$old")" ] && number "$total" && [ "$total" -le "$max" ] || exit 1
    written=0
    count=0
    : > "$tmp/new"
    while read -r kind offset length extra <&3; do
        [ -z "$extra" ] && number "$offset" && number "$length" && [ "$length" -gt 0 ] || exit 1
        written=$((written + length))
        [ "$written" -le "$total" ] && [ "$count" -lt 1024 ] || exit 1
        case $kind in
            copy)
                [ $((offset + length)) -le "$oldsize" ] || exit 1
                tail -c "+$((offset + 1))" "$old" | head -c "$length" >> "$tmp/new";;
            part)
                [ "$offset" = "$count" ] || exit 1
                unzip -p "$delta" "part-$count" | head -c "$length" >> "$tmp/new";;
            *) exit 1;;
        esac
        count=$((count + 1))
    done
    [ "$written" = "$total" ] && [ "$(bytes "$tmp/new")" -eq "$total" ] &&
        [ "$(sha "$tmp/new")" = "$expected" ] || { echo 'patch verification failed' >&2; exit 1; }
    mv -f -- "$tmp/new" "$dest"
)
