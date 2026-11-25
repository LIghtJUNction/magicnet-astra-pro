# Validate the private file as data. The core parses the IP and verifies TLS.
resolver_from_file() (
    file=$state/resolver
    [ -f "$file" ] && [ ! -L "$file" ] || exit 1
    owner=$(id -u) || exit 1
    case $(stat -c '%u:%a' "$file") in "$owner:600"|"$owner:400") ;; *) exit 1;; esac
    size=$(stat -c %s "$file") && [ "$size" -gt 0 ] && [ "$size" -le 512 ] || exit 1
    line=
    if IFS= read -r line < "$file"; then size=$((size - 1)); fi
    [ "$size" -eq "${#line}" ] || exit 1
    printf '%s\n' "$line" | grep -Eq '^tls://([0-9]+(\.[0-9]+){3}|\[[0-9A-Fa-f:.]+\]):[0-9]{1,5}\?server_name=[A-Za-z0-9.-]+$' || exit 1
    printf '%s' "$line"
)

load_resolver() {
    [ "${MAGICBOX_RESOLVER+x}" != x ] || return 0
    [ -e "$state/resolver" ] || [ -L "$state/resolver" ] || return 0
    MAGICBOX_RESOLVER=$(resolver_from_file) || { unset MAGICBOX_RESOLVER; error invalid_resolver; return 1; }
    export MAGICBOX_RESOLVER
}

# PID identity includes kernel start time and executable. A stale file from a
# previous boot or an unrelated process must never become a signal target.
start_ticks() {
    sed 's/^.*) //' "/proc/$1/stat" 2>/dev/null | awk '{ print $20 }'
}

owned_pid() {
    pidfile="${1:-$state/pid}"
    [ -r "$pidfile" ] && read -r pid ticks < "$pidfile" || return 1
    case $pid in ''|*[!0-9]*|0|1) return 1;; esac
    [ -n "$ticks" ] && [ "$(start_ticks "$pid")" = "$ticks" ] || return 1
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null) || return 1
    case $exe in "$core"|"$core (deleted)") ;; *) return 1;; esac
    printf '%s\n' "$pid"
    return 0
}

stop_daemon() {
    pidfile=$1
    old_pid=$(owned_pid "$pidfile") || { rm -f "$pidfile"; return 0; }
    kill "$old_pid" 2>/dev/null || ! owned_pid "$pidfile" >/dev/null || return 1
    tries=0
    while owned_pid "$pidfile" >/dev/null; do
        [ "$tries" -lt 40 ] || return 1
        sleep 0.05
        tries=$((tries + 1))
    done
    rm -f "$pidfile"
}

stop_core() { stop_daemon "$state/pid"; }

start_daemon() {
    pidfile=$1 logfile=$2 ready=$3
    shift 3
    owned_pid "$pidfile" >/dev/null && return 0
    [ -s "$config" ] || { error no_upstream; return 1; }
    "$core" check "$config" >/dev/null 2>&1 || { error invalid_config; return 1; }
    load_resolver || return 1
    : > "$logfile" || return 1
    # Do not retain the control lock or inherit the manager's stdin and pipes.
    nohup "$core" "$@" 9>&- </dev/null >"$logfile" 2>&1 &
    child=$!
    ticks=$(start_ticks "$child")
    [ -n "$ticks" ] || { error start_failed; return 1; }
    printf '%s %s\n' "$child" "$ticks" > "$pidfile.new" && mv "$pidfile.new" "$pidfile" || {
        kill "$child" 2>/dev/null
        return 1
    }
    tries=0
    while kill -0 "$child" 2>/dev/null && [ "$tries" -lt 160 ]; do
        if grep -Fxq "ready $ready" "$logfile" && owned_pid "$pidfile" >/dev/null; then return 0; fi
        tries=$((tries + 1))
        sleep 0.05
    done
    stop_daemon "$pidfile" || return 1
    error start_failed
    return 1
}

start_core() { start_daemon "$state/pid" "$state/core.log" "$listener" run "$config"; }

status() {
    if owned_pid >/dev/null; then echo 'state=running'; else echo 'state=stopped'; fi
    if [ -f "$state/enabled" ]; then echo 'autostart=yes'; else echo 'autostart=no'; fi
    printf 'listen=%s\n' "$listener"
    # Config is authored below. Strip all userinfo before emitting anything.
    endpoint=""
    if [ -s "$config" ]; then
        endpoint=$(sed -n 's/^upstream = "\([^"]*\)"$/\1/p' "$config")
    fi
    if [ -n "$endpoint" ]; then
        authority=${endpoint#*://}
        printf 'upstream=%s://%s\n' "${endpoint%%://*}" "${authority##*@}"
    else
        printf 'upstream=\n'
    fi
}

apply_candidate() {
    "$core" check "$work/new.toml" >/dev/null 2>&1 || { error invalid_config; return 1; }
    if [ -f "$config" ] && cmp -s "$work/new.toml" "$config"; then return 0; fi
    active=no
    if owned_pid >/dev/null; then
        load_resolver || return 1
        active=yes
        cp "$config" "$work/previous.toml" || return 1
        stop_daemon "$state/redirect.pid" && stop_core || { error stop_failed; return 1; }
    fi
    mv "$work/new.toml" "$config" || {
        [ "$active" = no ] || start_services
        return 1
    }
    if [ "$active" = yes ] && ! start_services; then
        stop_daemon "$state/redirect.pid" && stop_core || { error rollback_failed; return 1; }
        mv "$work/previous.toml" "$config" && start_services || { error rollback_failed; return 1; }
        error previous_config_restored
        return 1
    fi
}
