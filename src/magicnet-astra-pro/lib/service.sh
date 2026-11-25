# PID identity includes kernel start time and executable. A stale file from a
# previous boot or an unrelated process must never become a signal target.
start_ticks() {
    sed 's/^.*) //' "/proc/$1/stat" 2>/dev/null | awk '{ print $20 }'
}

owned_pid() {
    [ -r "$state/pid" ] && read -r pid ticks < "$state/pid" || return 1
    case $pid in ''|*[!0-9]*|0|1) return 1;; esac
    [ -n "$ticks" ] && [ "$(start_ticks "$pid")" = "$ticks" ] || return 1
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null) || return 1
    case $exe in "$core"|"$core (deleted)") ;; *) return 1;; esac
    printf '%s\n' "$pid"
    return 0
}

stop_core() {
    old_pid=$(owned_pid) || { rm -f "$state/pid"; return 0; }
    kill "$old_pid" 2>/dev/null || ! owned_pid >/dev/null || return 1
    tries=0
    while owned_pid >/dev/null; do
        [ "$tries" -lt 40 ] || return 1
        sleep 0.05
        tries=$((tries + 1))
    done
    rm -f "$state/pid"
}

start_core() {
    owned_pid >/dev/null && return 0
    [ -s "$config" ] || { error no_upstream; return 1; }
    "$core" check "$config" >/dev/null 2>&1 || { error invalid_config; return 1; }
    : > "$state/core.log" || return 1
    # Do not retain the control lock or inherit the manager's stdin and pipes.
    nohup "$core" run "$config" 9>&- </dev/null >"$state/core.log" 2>&1 &
    child=$!
    ticks=$(start_ticks "$child")
    [ -n "$ticks" ] || { error start_failed; return 1; }
    printf '%s %s\n' "$child" "$ticks" > "$state/pid.new" && mv "$state/pid.new" "$state/pid" || {
        kill "$child" 2>/dev/null
        return 1
    }
    tries=0
    while kill -0 "$child" 2>/dev/null && [ "$tries" -lt 80 ]; do
        if grep -Fxq "ready $listener" "$state/core.log" && owned_pid >/dev/null; then return 0; fi
        tries=$((tries + 1))
        sleep 0.05
    done
    stop_core || return 1
    error start_failed
    return 1
}

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
        active=yes
        cp "$config" "$work/previous.toml" || return 1
        stop_core || { error stop_failed; return 1; }
    fi
    mv "$work/new.toml" "$config" || {
        [ "$active" = no ] || start_core
        return 1
    }
    if [ "$active" = yes ] && ! start_core; then
        mv "$work/previous.toml" "$config" && start_core || { error rollback_failed; return 1; }
        error previous_config_restored
        return 1
    fi
}
