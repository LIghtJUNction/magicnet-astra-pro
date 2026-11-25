# Scope is explicit: app UID on OUTPUT and named tether interface on INPUT
# and FORWARD. A change is atomic per IP family; if IPv6 fails we undo IPv4.
dns_apps() {
    # PackageManager includes shared UIDs. Show the UID the firewall matches.
    cmd package list packages -U --user current > "$work/packages" 2>/dev/null ||
        pm list packages -U --user current > "$work/packages" 2>/dev/null ||
        { error app_list_unavailable; return 1; }
    awk '$1 ~ /^package:[A-Za-z0-9_.]+$/ && $2 ~ /^uid:[0-9]+$/ {
        uid=substr($2,5); if (uid+0 >= 10000) print uid,substr($1,9)
    }' "$work/packages" | sort -k2
}

dns_write_scope() {
    [ "$#" -gt 0 ] && [ "$#" -le 64 ] || { error invalid_scope; return 1; }
    for item do
        case $item in
            uid:*) value=${item#uid:}
                case $value in ''|0*|*[!0-9]*) error invalid_uid; return 1;; esac
                [ "${#value}" -le 10 ] && [ "$value" -ge 10000 ] && [ "$value" -le 2147483647 ] ||
                    { error invalid_uid; return 1; }
                printf 'uid %s\n' "$value";;
            app:*) value=${item#app:}
                case $value in ''|*[!a-zA-Z0-9_.]*) error invalid_package; return 1;; esac
                if [ ! -f "$work/apps" ]; then dns_apps > "$work/apps" || return 1; fi
                uid=$(awk -v name="$value" '$2==name {print $1; exit}' "$work/apps")
                [ -n "$uid" ] || { error package_not_found; return 1; }
                printf 'uid %s\n' "$uid";;
            tether:*) value=${item#tether:}
                case $value in ''|*[!a-zA-Z0-9_.-]*|-*|.*) error invalid_interface; return 1;; esac
                [ "${#value}" -le 15 ] || { error invalid_interface; return 1; }
                printf 'tether %s\n' "$value";;
            *) error invalid_scope; return 1;;
        esac
    done
}

dns_xt() {
    # Android netd takes the same xtables lock. Restore input must be reopened
    # for every retry. Other errors (syntax, unavailable matches) fail at once.
    stdin=$1
    shift
    attempts=0
    while :; do
        "$@" < "$stdin" 2> "$work/xt-error" && return 0
        if [ "$attempts" -ge 32 ] || ! grep -Ei 'xtables lock|resource temporarily unavailable' "$work/xt-error" >/dev/null; then
            cat "$work/xt-error" >&2
            return 1
        fi
        attempts=$((attempts+1))
        sleep 0.15
    done
}

dns_tools() {
    # AOSP 6 builds both complete restore entrypoints into the family
    # binaries but omits the usual restore symlinks. Probe the applet help
    # before using it. A standalone iptables binary cannot satisfy this.
    mkdir -p "$work/tools" || return 1
    for family in iptables ip6tables; do
        exe=$(command -v "$family") || { error firewall_unavailable; return 1; }
        if ! command -v "$family-restore" >/dev/null; then
            ln -sf "$exe" "$work/tools/$family-restore" &&
                "$work/tools/$family-restore" --help 2>&1 | grep -q -- '--noflush' ||
                { error firewall_unavailable; return 1; }
        fi
    done
    PATH="$work/tools:$PATH"
    export PATH
}

# Apply one table per family. A durable intent allows a boot retry after
# interruption. A temporary withdrawal leaves the chosen scope in place.
firewall_commit() {
    policy=$1 table=$2 persist=${3:-yes}
    dns_tools || return 1
    families='iptables ip6tables'
    if [ "$policy" = traffic ] && [ "${traffic_mode:-}" = ipv4-redirect-ipv6-block ]; then families=iptables; fi
    for family in $families; do
        local_routes=
        if [ "$policy" = traffic ] && grep -q '^tether ' "$work/scope"; then
            local_routes="$work/$family.local"
            traffic_local_routes "$family" "$local_routes" || return 1
        fi
        command -v "$family-restore" >/dev/null &&
            dns_xt /dev/null "$family" -t "$table" -S > "$work/$family.snapshot" ||
            { error firewall_unavailable; return 1; }
        for undo in 0 1; do
            awk -v undo="$undo" -v policy="$policy" -v family="$family" -v local_routes="$local_routes" -v upstream="${bypass_ip:-}" \
                -f "$root/lib/firewall-restore.awk" -f "$root/lib/traffic-rules.awk" "$work/scope" "$work/$family.snapshot" \
                > "$work/$family.$undo" || { error firewall_ownership_conflict; return 1; }
        done
    done
    # A crash between commits leaves enough intent for 'dns sync' or boot.
    if [ "$persist" = yes ]; then
        cp "$work/scope" "$state/$policy-next.new" && mv "$state/$policy-next.new" "$state/$policy-next" || return 1
    fi
    if ! dns_xt "$work/iptables.0" iptables-restore -n; then
        [ "$persist" = no ] || rm -f "$state/$policy-next"
        error ipv4_rules_rejected
        return 1
    fi
    if [ "$families" != iptables ] && ! dns_xt "$work/ip6tables.0" ip6tables-restore -n; then
        if dns_xt "$work/iptables.1" iptables-restore -n; then
            [ "$persist" = no ] || rm -f "$state/$policy-next"
            error ipv6_rules_rejected
        else
            : > "$work/recovery"
            error firewall_recovery_required
        fi
        return 1
    fi
    [ "$persist" = yes ] || return 0
    mv "$state/$policy-next" "$state/$policy-scope" || return 1
    [ -s "$state/$policy-scope" ] || rm -f "$state/$policy-scope"
}

dns_manage() {
    case ${1:-status} in
        apps) dns_apps;;
        capabilities)
            dns_tools || return 1
            dns_xt /dev/null iptables -t filter -S >/dev/null && dns_xt /dev/null ip6tables -t filter -S >/dev/null ||
                { error firewall_unavailable; return 1; };;
        status)
            if [ -f "$state/dns-next" ]; then echo 'pending=yes'; else echo 'pending=no'; fi
            if [ -s "$state/dns-scope" ]; then cat "$state/dns-scope"; else echo 'scope=empty'; fi;;
        apply)
            shift
            dns_write_scope "$@" > "$work/raw" && sort -u "$work/raw" > "$work/scope" && firewall_commit dns filter;;
        clear)
            : > "$work/scope" && firewall_commit dns filter;;
        sync)
            if [ -f "$state/dns-next" ]; then cp "$state/dns-next" "$work/scope" || return 1
            elif [ -s "$state/dns-scope" ]; then cp "$state/dns-scope" "$work/scope" || return 1
            else return 0; fi
            firewall_commit dns filter;;
        *) error invalid_scope; return 2;;
    esac
}
