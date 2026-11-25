# The module's resolver policy also applies to downloading subscriptions.
# An initial local file or literal endpoint bootstraps the first connection.
fetch_source() {
    url=$1
    ua=$2
    case $url in https://?*) ;; *) error https_required; return 1;; esac
    case $url in *[![:graph:]]*|*\"*|*\\*) error invalid_url; return 1;; esac
    case $ua in *[![:print:]]*|*\"*|*\\*) error invalid_ua; return 1;; esac
    [ "${#url}" -le 4096 ] && [ "${#ua}" -le 256 ] || { error input_too_large; return 1; }
    if [ ! -s "$config" ]; then
        printf '%s\n' "$url" | MAGICBOX_USER_AGENT="$ua" "$core" fetch - > "$work/input" 2>/dev/null ||
            { error fetch_failed; return 1; }
        return 0
    fi
    owned_pid >/dev/null || { error proxy_required; return 1; }
    command -v curl >/dev/null || { error curl_required; return 1; }
    # curl config on stdin keeps token-bearing URLs out of the curl process argv.
    printf 'url = "%s"\nuser-agent = "%s"\n' "$url" "$ua" |
        (ulimit -f 4096 && curl -q --silent --fail --location --max-redirs 4 --max-time 25 \
            --proto '=https' --proto-redir '=https' --proxy "socks5h://$listener" --noproxy '' \
            --max-filesize 2097152 --output "$work/input" --config -) 2>/dev/null ||
        { error fetch_failed; return 1; }
}

load_source() {
    case $1 in
        -) head -c 2097153 > "$work/input";;
        *) [ -f "$1" ] && head -c 2097153 < "$1" > "$work/input";;
    esac || { error file_unreadable; return 1; }
}

unpack_input() {
    [ -s "$work/input" ] && [ "$(wc -c < "$work/input")" -le 2097152 ] ||
        { error input_too_large_or_empty; return 1; }
    source_file="$work/input"
    if head -c 32 "$source_file" | grep -aqE '^(age-encryption.org/v1|-----BEGIN AGE ENCRYPTED FILE---)'; then
        [ -r "${MAGICNET_AGE_IDENTITY:-$state/identity.txt}" ] ||
            { error age_identity_required; return 1; }
        command -v age >/dev/null || { error age_required; return 1; }
        (ulimit -f 4096 && age -d -i "${MAGICNET_AGE_IDENTITY:-$state/identity.txt}" \
            "$source_file" >"$work/plain") 2>/dev/null || { error decrypt_failed; return 1; }
        source_file="$work/plain"
    fi
    return 0
}

preview_input() {
    unpack_input || return 1
    "$core" import --list "$source_file" > "$work/nodes" 2>/dev/null || { error import_failed; return 1; }
    token=$(od -An -tx1 -N12 /dev/urandom | tr -d ' \n') || return 1
    [ "${#token}" -eq 24 ] || return 1
    # Keep the original encrypted feed encrypted at rest. Hold one private
    # preview and use the same bytes at selection time, even if a server rotates.
    rm -f "$state"/preview-feed.* || return 1
    mv "$work/input" "$state/preview-feed.$token" || return 1
    printf 'preview=%s\n' "$token"
    cat "$work/nodes"
}

apply_preview() {
    case $1 in *[!a-f0-9]*) error stale_preview; return 1;; esac
    [ "${#1}" -eq 24 ] && [ -f "$state/preview-feed.$1" ] || { error stale_preview; return 1; }
    mv "$state/preview-feed.$1" "$work/input" && apply_input "$2"
}

apply_input() {
    case $1 in ''|*[!0-9]*|0) error invalid_index; return 1;; esac
    unpack_input || return 1
    cat "$root/default.toml" > "$work/new.toml" || return 1
    "$core" import --select "$1" "$source_file" >> "$work/new.toml" 2>/dev/null ||
        { error import_failed; return 1; }
    apply_candidate
}
