# The module owns a nonpersistent TUN descriptor, one table and one rule per
# IP family. Root-owned SOCKS and upstream connections use the normal routes.
tun_table=19871
tun_pref=9000
tun_uids=10000-4294967294
tun_guard_metric=42760
tun_bin="$root/bin/hev-socks5-tunnel"
tun_ip=/system/bin/ip
[ -x "$tun_ip" ] || tun_ip=ip

configured_mode() {
    if [ -f "$state/mode" ]; then
        case $(cat "$state/mode") in tun) echo tun;; local) echo local;; *) error invalid_mode; return 1;; esac
    elif [ -s "$config" ]; then
        # A pre-TUN installation keeps its existing routing policy on upgrade.
        echo local
    else
        echo tun
    fi
}

save_mode() {
    printf '%s\n' "$1" > "$work/mode" && mv "$work/mode" "$state/mode"
}

tun_rule() {
    "$tun_ip" "$1" rule "$2" pref "$tun_pref" iif lo uidrange "$tun_uids" lookup "$tun_table"
}

tun_rule_present() (
    rules=$("$tun_ip" "$1" rule show) || exit 2
    printf '%s\n' "$rules" | awk -v p="$tun_pref:" -v u="$tun_uids" -v t="$tun_table" '
        $1==p && $2=="from" && $3=="all" {
            iif=uid=tab=0
            for(i=4;i<NF;i+=2) {
                if ($i=="iif" && $(i+1)=="lo") iif=1
                else if ($i=="uidrange" && $(i+1)==u) uid=1
                else if ($i=="lookup" && $(i+1)==t) tab=1
                else if ($i!="proto" && $i!="protocol") next
            }
            if(iif && uid && tab) found=1
        }
        END{ exit !found }'
)

tun_guard() {
    "$tun_ip" "$1" route "$2" unreachable default metric "$tun_guard_metric" table "$tun_table"
}

tun_guard_present() {
    printf '%s\n' "$1" | grep -Eq "^unreachable default .*metric $tun_guard_metric( |$)"
}

tun_link_ready() {
    owned_pid "$state/tun.pid" >/dev/null &&
        "$tun_ip" link show dev magicnet0 2>/dev/null | grep -Eq '(<|,)UP(,|>)' &&
        "$tun_ip" -4 addr show dev magicnet0 2>/dev/null | grep -q 'inet 198.18.0.1/' &&
        "$tun_ip" -6 addr show dev magicnet0 2>/dev/null | grep -q 'inet6 fd00:198:18::1/'
}

tun_ready() (
    tun_link_ready || exit 1
    for af in -4 -6; do
        tun_rule_present "$af" || exit 1
        routes=$("$tun_ip" "$af" route show table "$tun_table" 2>/dev/null) || exit 1
        printf '%s\n' "$routes" | grep -Eq '^default dev magicnet0( |$)' && tun_guard_present "$routes" || exit 1
    done
)

# Replies injected by the tunnel return over a different interface from
# the root UID's upstream route. Linux uses max(all, interface) for RPF.
tun_return_path() (
    path=/proc/sys/net/ipv4/conf/magicnet0/rp_filter
    global=$(cat /proc/sys/net/ipv4/conf/all/rp_filter) && device=$(cat "$path") || exit 1
    case "$global:$device" in
        0:0|0:2|1:2|2:0|2:1|2:2) exit 0;;
        0:1|1:0|1:1) printf '2\n' > "$path" && [ "$(cat "$path")" = 2 ];;
        *) exit 1;;
    esac
)

tun_preflight() (
    [ -x "$tun_bin" ] || { error tun_engine_missing; exit 1; }
    [ "$(id -u)" = 0 ] || { error tun_root_required; exit 1; }
    links=$("$tun_ip" link show) || { error tun_ip_unavailable; exit 1; }
    if printf '%s\n' "$links" | grep -Eq '^[0-9]+: magicnet0[:@]'; then error tun_conflict; exit 1; fi
    for af in -4 -6; do
        rules=$("$tun_ip" "$af" rule show) && routes=$("$tun_ip" "$af" route show table all) ||
            { error tun_ip_unavailable; exit 1; }
        if printf '%s\n' "$rules" | grep -Eq "^$tun_pref:| lookup $tun_table( |$)" ||
           printf '%s\n' "$routes" | grep -Eq "(^| )table $tun_table( |$)"; then
            error tun_conflict
            exit 1
        fi
    done
)

tun_stop() (
    for af in -6 -4; do
        marker="$state/tun.policy$af"
        [ -f "$marker" ] || continue
        boot=$(cat /proc/sys/kernel/random/boot_id) || exit 1
        if [ "$(cat "$marker")" = "$boot" ]; then
            if tun_rule_present "$af"; then
                tun_rule "$af" del || { error tun_cleanup_failed; exit 1; }
            elif [ "$?" -ne 1 ]; then error tun_cleanup_failed; exit 1; fi
            routes=$("$tun_ip" "$af" route show table all) || { error tun_cleanup_failed; exit 1; }
            guards=$(printf '%s\n' "$routes" | grep -E " table $tun_table( |$)") || guards=
            if tun_guard_present "$guards"; then
                tun_guard "$af" del || { error tun_cleanup_failed; exit 1; }
            fi
        fi
        rm -f "$marker" || exit 1
    done
    # The kernel disposes of the exact link and its routes when its last
    # descriptor closes. Never delete an interface or flush a table by name.
    stop_daemon "$state/tun.pid"
)

tun_start() (
    tun_ready && exit 0
    tun_stop && tun_preflight || exit 1
    boot=$(cat /proc/sys/kernel/random/boot_id) && [ -n "$boot" ] || exit 1
    nohup "$tun_bin" "$root/tun.yml" 9>&- </dev/null >"$state/tun.log" 2>&1 &
    child=$!
    ticks=$(start_ticks "$child")
    if [ -z "$ticks" ] || ! printf '%s %s\n' "$child" "$ticks" > "$work/tun.pid" ||
        ! mv "$work/tun.pid" "$state/tun.pid"; then
        kill "$child" 2>/dev/null
        error tun_start_failed
        exit 1
    fi
    tries=0
    until tun_link_ready; do
        [ "$(start_ticks "$child")" = "$ticks" ] && [ "$tries" -lt 80 ] || {
            tun_stop; error tun_start_failed; exit 1
        }
        tries=$((tries + 1))
        sleep 0.05
    done
    tun_return_path || { tun_stop; error tun_route_failed; exit 1; }
    for af in -4 -6; do
        # The unreachable route survives a crashed engine. An empty table
        # would fall through to the physical network until stop or recovery.
        if ! printf '%s\n' "$boot" > "$work/policy" || ! mv "$work/policy" "$state/tun.policy$af" ||
            ! tun_guard "$af" add ||
            ! "$tun_ip" "$af" route add default dev magicnet0 table "$tun_table"; then
            tun_stop; error tun_route_failed; exit 1
        fi
    done
    for af in -4 -6; do
        tun_rule "$af" add || { tun_stop; error tun_rule_failed; exit 1; }
    done
    tun_ready || { tun_stop; error tun_start_failed; exit 1; }
)

set_mode() {
    case $1 in tun|local) ;; *) error invalid_mode; return 2;; esac
    current_mode=$(configured_mode) || return 1
    if owned_pid >/dev/null; then
        case $1 in tun) tun_start || return 1;; local) tun_stop || return 1;; esac
    else
        # Reconcile stale resources left by a failed/stopped service.
        tun_stop || return 1
    fi
    if ! save_mode "$1"; then
        if owned_pid >/dev/null; then
            case $current_mode in tun) tun_start || error rollback_failed;; local) tun_stop || error rollback_failed;; esac
        fi
        return 1
    fi
}

mode_status() {
    configured=$(configured_mode) || configured=unknown
    printf 'configured_mode=%s\n' "$configured"
    if owned_pid >/dev/null; then
        if tun_ready; then effective=tun
        elif [ "$configured" = local ] && [ ! -f "$state/tun.pid" ]; then effective=local
        else effective=degraded; fi
    elif [ -f "$state/tun.policy-4" ] || [ -f "$state/tun.policy-6" ] || owned_pid "$state/tun.pid" >/dev/null; then
        effective=degraded
    else effective=off; fi
    printf 'effective_mode=%s\n' "$effective"
    case $effective in off) echo state=stopped;; degraded) echo state=degraded;; *) echo state=running;; esac
}
