traffic_chosen() { [ -e "$state/traffic-next" ] || [ -s "$state/traffic-scope" ]; }

traffic_local_routes() {
    case $1 in iptables) af=-4;; ip6tables) af=-6;; *) return 1;; esac
    ip_tool=/system/bin/ip
    if [ ! -x "$ip_tool" ]; then ip_tool=$(command -v ip) || { error local_routes_unavailable; return 1; }; fi
    "$ip_tool" "$af" route show table local type local > "$work/kernel-routes" &&
        awk -v family="$1" -f "$root/lib/local-routes.awk" "$work/kernel-routes" > "$2" ||
        { error local_routes_unavailable; return 1; }
}

traffic_restore_intent() {
    [ "$remember" = yes ] || return 0
    if [ -e "$work/traffic-prior" ]; then
        mv "$work/traffic-prior" "$state/traffic-next"
    else
        rm -f "$state/traffic-next"
    fi
}

# Protect scoped DNS before admitting redirected TCP. Keep inverse filter
# transactions until both NAT families have accepted the new scope.
traffic_commit() {
    remember=$1
    dns_tools || return 1
    traffic_mode=dual-stack-redirect
    if ! dns_xt /dev/null ip6tables -t nat -S >/dev/null 2>"$work/traffic-probe"; then
        if grep -Eqi '(table does not exist|table not found)' "$work/traffic-probe"; then
            traffic_mode=ipv4-redirect-ipv6-block
        else
            cat "$work/traffic-probe" >&2; error firewall_unavailable; return 1
        fi
    fi
    if [ "$remember" = yes ]; then
        rm -f "$work/traffic-prior"
        if [ -e "$state/traffic-next" ]; then cp "$state/traffic-next" "$work/traffic-prior" || return 1; fi
        cp "$work/scope" "$state/traffic-next.new" && mv "$state/traffic-next.new" "$state/traffic-next" || return 1
    fi
    if ! firewall_commit guard filter no; then
        [ -e "$work/recovery" ] || traffic_restore_intent
        return 1
    fi
    for fw in iptables ip6tables; do cp "$work/$fw.1" "$work/$fw.guard-undo" || return 1; done
    if ! firewall_commit traffic nat no; then
        [ ! -e "$work/recovery" ] || return 1
        for fw in iptables ip6tables; do
            dns_xt "$work/$fw.guard-undo" "$fw-restore" -n || { error firewall_recovery_required; return 1; }
        done
        traffic_restore_intent
        return 1
    fi
    if [ -s "$work/scope" ]; then
        printf '%s\n' "$traffic_mode" > "$state/traffic-mode.new" && mv "$state/traffic-mode.new" "$state/traffic-mode" || return 1
    else rm -f "$state/traffic-mode"; fi
    [ "$remember" = yes ] || return 0
    mv "$state/traffic-next" "$state/traffic-scope" || return 1
    [ -s "$state/traffic-scope" ] || rm -f "$state/traffic-scope"
}

traffic_install() {
    [ -s "$work/scope" ] || {
        traffic_commit yes && stop_daemon "$state/redirect.pid"
        return
    }
    owned_pid >/dev/null || { error proxy_required; return 1; }
    # Configuration written by configure/import is canonical. Isolate the
    # numeric authority. Credentials and TLS parameters never enter the rules.
    endpoint=$(sed -n 's/^upstream = "\([^"]*\)"$/\1/p' "$config")
    hostport=${endpoint#*://}; hostport=${hostport##*@}; hostport=${hostport%%\?*}
    case $hostport in
        \[*\]:*) bypass_ip=${hostport%%\]*}; bypass_ip=${bypass_ip#\[};;
        *:*) bypass_ip=${hostport%:*};;
        *) error invalid_config; return 1;;
    esac
    # "check" validates domain syntax. Named peers resolve and pin inside
    # magicbox using authenticated DNS. Never send them to xtables/getaddrinfo.
    case $bypass_ip in
        *:*) case $bypass_ip in *[!0-9a-fA-F:]*) error invalid_config; return 1;; esac;;
        *[!0-9.]*) bypass_ip=;;
        '') error invalid_config; return 1;;
    esac
    was_redirect=no
    if owned_pid "$state/redirect.pid" >/dev/null; then was_redirect=yes; fi
    start_daemon "$state/redirect.pid" "$state/redirect.log" '[::]:19870' redirect "$config" 19870 || return 1
    if traffic_commit yes; then return 0; fi
    # Keep serving the previous scope when a replacement transaction fails.
    if [ "$was_redirect" = no ] && ! traffic_chosen; then stop_daemon "$state/redirect.pid"; fi
    return 1
}

traffic_sync() {
    if [ -f "$state/traffic-next" ]; then cp "$state/traffic-next" "$work/scope" || return 1
    elif [ -s "$state/traffic-scope" ]; then cp "$state/traffic-scope" "$work/scope" || return 1
    else return 0; fi
    case ${1:-route} in
        guard) firewall_commit guard filter no;;
        route) traffic_install;;
    esac
}

start_services() {
    started=no
    if ! owned_pid >/dev/null; then start_core || return 1; started=yes; fi
    if traffic_sync; then return 0; fi
    if [ "$started" = yes ]; then stop_daemon "$state/redirect.pid" && stop_core; fi
    return 1
}

traffic_suspend() {
    if traffic_chosen; then
        : > "$work/scope" && traffic_commit no || return 1
    fi
    stop_daemon "$state/redirect.pid"
}

traffic_manage() {
    case ${1:-status} in
        apps) dns_apps > "$work/all-apps" && awk '$1 % 100000 >= 10000' "$work/all-apps";;
        status)
            if owned_pid "$state/redirect.pid" >/dev/null; then echo 'redirect=running'; else echo 'redirect=stopped'; fi
            if [ -f "$state/traffic-mode" ]; then printf 'mode=%s\n' "$(cat "$state/traffic-mode")"; else echo 'mode=off'; fi
            if [ -f "$state/traffic-next" ]; then echo 'pending=yes'; else echo 'pending=no'; fi
            if [ -s "$state/traffic-scope" ]; then cat "$state/traffic-scope"; else echo 'scope=empty'; fi;;
        apply)
            shift
            for item do
                case $item in
                    tether:lo|tether:tun*|tether:tailscale*|tether:wg*|tether:warp*|tether:WARP*|tether:ipsec*|tether:xfrm*|tether:ppp*|tether:rmnet*|tether:ccmni*|tether:wwan*)
                        error invalid_interface; return 1;;
                esac
            done
            dns_write_scope "$@" > "$work/raw" || return 1
            # Per-user Android UIDs contain a 100000-wide app ID field.
            awk '$1=="uid" && $2 % 100000 < 10000 { exit 1 }' "$work/raw" ||
                { error invalid_uid; return 1; }
            sort -u "$work/raw" > "$work/scope" && traffic_install;;
        clear)
            if traffic_chosen; then
                : > "$work/scope" && traffic_install
            else stop_daemon "$state/redirect.pid"; fi;;
        sync) traffic_sync;;
        *) error invalid_scope; return 2;;
    esac
}
