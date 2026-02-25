#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
# Information Crawler — 统一部署管理脚本
#
# 用法:
#   ./deploy.sh              智能部署（检测状态，该装装该启启）
#   ./deploy.sh deploy       同上
#   ./deploy.sh start        启动服务
#   ./deploy.sh stop         停止服务
#   ./deploy.sh restart      重启服务
#   ./deploy.sh status       查看详细状态
#   ./deploy.sh logs [-f]    查看日志
#   ./deploy.sh init         仅初始化（不启动）
#   ./deploy.sh help         帮助信息
# ══════════════════════════════════════════════════════════════
set -euo pipefail

# ── Constants ─────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PID_FILE="$PROJECT_DIR/.service.pid"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/server.log"
VERSION=$(grep '^version' "$PROJECT_DIR/pyproject.toml" 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/' || echo "0.0.0")

# Defaults
PORT=8001
WORKERS=1
TAIL_LINES=50
FOLLOW=false
PRODUCTION=false

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── UI Helpers ────────────────────────────────────────────────
W=62  # box width

_repeat() { printf '%*s' "$1" '' | tr ' ' "$2"; }

badge_ok()   { printf "${GREEN}[  OK  ]${NC}"; }
badge_warn() { printf "${YELLOW}[ WARN ]${NC}"; }
badge_fail() { printf "${RED}[ FAIL ]${NC}"; }
badge_skip() { printf "${DIM}[ SKIP ]${NC}"; }

show_header() {
    local line
    line=$(_repeat $((W - 2)) "═")
    echo ""
    printf "${CYAN}╔${line}╗${NC}\n"
    printf "${CYAN}║${NC}                                                            ${CYAN}║${NC}\n"
    printf "${CYAN}║${NC}${BOLD}   Information Crawler  v%s${NC}%*s${CYAN}║${NC}\n" "$VERSION" $((W - 29 - ${#VERSION})) ""
    printf "${CYAN}║${NC}   中关村人工智能研究院 · 信息监测系统              ${CYAN}║${NC}\n"
    printf "${CYAN}║${NC}                                                            ${CYAN}║${NC}\n"
    printf "${CYAN}╚${line}╝${NC}\n"
    echo ""
}

section_open() {
    local title="$1"
    local tlen=${#title}
    local dash_right=$((W - 6 - tlen))
    printf "${BLUE}┌─── %s $(_repeat $dash_right "─")┐${NC}\n" "$title"
    echo ""
}

section_mid() {
    local title="$1"
    local tlen=${#title}
    local dash_right=$((W - 6 - tlen))
    echo ""
    printf "${BLUE}├─── %s $(_repeat $dash_right "─")┤${NC}\n" "$title"
    echo ""
}

section_close() {
    local line
    line=$(_repeat $((W - 2)) "─")
    echo ""
    printf "${BLUE}└${line}┘${NC}\n"
}

# Print step line: "  [1/7]  message ............. "  (no newline)
step() {
    local n="$1" total="$2" msg="$3"
    local prefix
    prefix=$(printf "  [%d/%d]  %s " "$n" "$total" "$msg")
    local plen=${#prefix}
    local dots=$((W - plen - 10))
    [[ $dots -lt 3 ]] && dots=3
    printf "%s%s " "$prefix" "$(_repeat $dots ".")"
}

# Print sub-item: "         ├ key .............. "
sub_item() {
    local key="$1" last="${2:-false}"
    local sym="├"
    [[ "$last" == "true" ]] && sym="└"
    local prefix
    prefix=$(printf "         %s %s " "$sym" "$key")
    local plen=${#prefix}
    local dots=$((W - plen - 10))
    [[ $dots -lt 3 ]] && dots=3
    printf "%s%s " "$prefix" "$(_repeat $dots ".")"
}

info()    { printf "  ${DIM}%s${NC}\n" "$*"; }
success() { printf "  ${GREEN}✓  %s${NC}\n" "$*"; }
warning() { printf "  ${YELLOW}⚠  %s${NC}\n" "$*"; }
error()   { printf "  ${RED}✗  %s${NC}\n" "$*"; }

spinner() {
    local pid=$1 msg="$2"
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}%s${NC} %s" "${frames:i%${#frames}:1}" "$msg"
        i=$((i + 1))
        sleep 0.12
    done
    printf "\r%*s\r" $((${#msg} + 6)) ""
}

# ── Environment Functions ─────────────────────────────────────
validate_python() {
    local ver
    ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        printf "Python %s" "$ver"
        return 0
    else
        printf "Python %s (需要 >= 3.11)" "$ver"
        return 1
    fi
}

# ensure_venv [--create]
# --create: create venv if missing (for deploy/init)
# without --create: fail if missing (for start/stop/etc)
ensure_venv() {
    local create=false
    [[ "${1:-}" == "--create" ]] && create=true

    # Already inside correct venv
    if [[ -n "${VIRTUAL_ENV:-}" && "$VIRTUAL_ENV" == "$VENV_DIR" ]]; then
        return 0
    fi

    # Venv exists — activate
    if [[ -d "$VENV_DIR" && -f "$VENV_DIR/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        return 0
    fi

    # Venv does not exist
    if [[ "$create" == "true" ]]; then
        python3 -m venv "$VENV_DIR" 2>/dev/null
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip --quiet 2>/dev/null
        return 0
    else
        return 1
    fi
}

validate_env() {
    local status=0

    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        if [[ -f "$PROJECT_DIR/.env.example" ]]; then
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
            printf "created from .env.example"
        else
            printf "missing"
            return 1
        fi
        return 0
    fi

    # Clean garbage lines (vim/editor typos)
    if grep -qE '^(exit\(\)|q|:q|:wq|:x)\s*$' "$PROJECT_DIR/.env" 2>/dev/null; then
        if [[ "$(uname)" == "Darwin" ]]; then
            sed -i '' '/^exit()$/d; /^q$/d; /^:q$/d; /^:wq$/d; /^:x$/d' "$PROJECT_DIR/.env"
        else
            sed -i '/^exit()$/d; /^q$/d; /^:q$/d; /^:wq$/d; /^:x$/d' "$PROJECT_DIR/.env"
        fi
        printf "cleaned"
    else
        printf "ok"
    fi
    return $status
}

check_env_key() {
    local key="$1"
    if grep -q "${key}=.\+" "$PROJECT_DIR/.env" 2>/dev/null; then
        return 0
    fi
    return 1
}

install_deps() {
    cd "$PROJECT_DIR"
    pip install -e ".[dev]" --quiet 2>&1 | tail -1 &
    local pid=$!
    spinner $pid "Installing dependencies..."
    wait $pid 2>/dev/null
    return ${PIPESTATUS[0]:-0}
}

check_playwright() {
    # Test if chromium is usable
    if python3 -c "
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
try:
    b = pw.chromium.launch(headless=True)
    b.close()
finally:
    pw.stop()
" 2>/dev/null; then
        return 0
    fi
    return 1
}

install_playwright() {
    playwright install chromium --with-deps 2>/dev/null &
    local pid=$!
    spinner $pid "Installing Playwright Chromium..."
    wait $pid 2>/dev/null
    if [[ $? -ne 0 ]]; then
        playwright install chromium 2>/dev/null &
        pid=$!
        spinner $pid "Retrying without --with-deps..."
        wait $pid 2>/dev/null
    fi
}

ensure_directories() {
    local dirs=(
        "data/raw"
        "data/processed/policy_intel"
        "data/processed/personnel_intel"
        "data/processed/tech_frontier"
        "data/processed/university_eco"
        "data/processed/daily_briefing"
        "data/state"
        "data/logs"
        "logs"
    )
    for dir in "${dirs[@]}"; do
        mkdir -p "$PROJECT_DIR/$dir"
    done
}

# ── Service Functions ─────────────────────────────────────────
_is_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    return 1
}

_get_pid() { cat "$PID_FILE" 2>/dev/null || echo ""; }

_pids_on_port() { lsof -ti "tcp:$PORT" 2>/dev/null || true; }

_free_port() {
    local pids
    pids=$(_pids_on_port)
    [[ -z "$pids" ]] && return 0

    warning "Port $PORT occupied (PIDs: $(echo "$pids" | tr '\n' ' '))"
    echo "$pids" | xargs kill 2>/dev/null || true
    sleep 2
    pids=$(_pids_on_port)
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
    pids=$(_pids_on_port)
    if [[ -n "$pids" ]]; then
        error "Cannot free port $PORT"
        return 1
    fi
}

_wait_for_health() {
    local max_wait=30 waited=0
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    printf "  Waiting for health check "
    while [[ $waited -lt $max_wait ]]; do
        if curl -sf "http://localhost:$PORT/api/v1/health/" >/dev/null 2>&1; then
            printf "\r"
            step "$1" "$2" "Health check"
            badge_ok
            printf "\n"
            return 0
        fi
        printf "\b${CYAN}%s${NC}" "${frames:waited%${#frames}:1}"
        sleep 1
        waited=$((waited + 1))
    done
    printf "\r"
    step "$1" "$2" "Health check"
    badge_warn
    printf "\n"
    info "Service may still be initializing (${max_wait}s timeout)"
}

_launch_uvicorn() {
    mkdir -p "$LOG_DIR"
    _free_port || return 1
    rm -f "$PID_FILE"

    local extra_args=()
    local mode="production"
    if [[ "$PRODUCTION" != "true" && "$WORKERS" -eq 1 ]]; then
        extra_args+=(--reload)
        mode="development"
    fi

    cd "$PROJECT_DIR"
    nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --workers "$WORKERS" \
        "${extra_args[@]}" \
        >> "$LOG_FILE" 2>&1 &

    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        printf "%s  PID %s" "$(badge_ok)" "$pid"
        return 0
    else
        badge_fail
        printf "  see %s" "$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# ── Status Display ────────────────────────────────────────────
show_service_status() {
    section_open "Service Status"

    if _is_running; then
        local pid etime cpu mem
        pid=$(_get_pid)
        etime=$(ps -p "$pid" -o etime= 2>/dev/null | xargs || echo "N/A")
        cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | xargs || echo "N/A")
        mem=$(ps -p "$pid" -o rss= 2>/dev/null | xargs || echo "0")
        local mem_mb
        mem_mb=$(echo "$mem" | awk '{printf "%.1f", $1/1024}')

        printf "  ${BOLD}Status:${NC}    ${GREEN}● Running${NC}%*s" 19 ""
        printf "${BOLD}Port:${NC} %s\n" "$PORT"
        printf "  ${BOLD}PID:${NC}       %-*s" 28 "$pid"
        printf "${BOLD}Workers:${NC} %s\n" "$WORKERS"
        printf "  ${BOLD}Uptime:${NC}    %-*s" 28 "$etime"
        printf "${BOLD}CPU:${NC} %s%%\n" "$cpu"
        printf "  ${BOLD}Memory:${NC}    %s MB\n" "$mem_mb"
        echo ""
        printf "  ${DIM}API Docs:${NC}  http://localhost:%s/docs\n" "$PORT"
        printf "  ${DIM}Health:${NC}    http://localhost:%s/api/v1/health/\n" "$PORT"
    else
        printf "  ${BOLD}Status:${NC}    ${RED}● Stopped${NC}\n"
    fi
}

show_pipeline_status() {
    local response
    response=$(curl -sf "http://localhost:$PORT/api/v1/health/pipeline-status" 2>/dev/null) || return 0

    local status
    status=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")

    section_mid "Pipeline"

    if [[ "$status" == "never_run" ]]; then
        printf "  ${YELLOW}○${NC} Pipeline has not run yet\n"
        info "It will auto-trigger on first start, or manually:"
        info "curl -X POST http://localhost:$PORT/api/v1/health/pipeline-trigger"
    elif [[ "$status" == "success" ]]; then
        printf "  ${GREEN}●${NC} Last run: ${GREEN}success${NC}\n"
        echo "$response" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for s in d.get('stages', []):
    icon = '✓' if s.get('status') == 'success' else ('⊘' if s.get('status') == 'skipped' else '✗')
    color = '32' if s.get('status') == 'success' else ('90' if s.get('status') == 'skipped' else '31')
    dur = s.get('duration_seconds', 0)
    dur_str = f'{dur:.1f}s' if dur else ''
    print(f'  \033[{color}m{icon}\033[0m  {s[\"name\"]:<30} {dur_str}')
" 2>/dev/null || true
    else
        printf "  ${RED}●${NC} Last run: ${RED}%s${NC}\n" "$status"
        echo "$response" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for s in d.get('stages', []):
    if s.get('status') == 'failed':
        print(f'  \033[31m✗\033[0m  {s[\"name\"]}: {s.get(\"error\", \"unknown\")}')
" 2>/dev/null || true
    fi
}

show_data_stats() {
    section_mid "Processed Data"

    local modules=("policy_intel:Policy Intel" "personnel_intel:Personnel Intel" "tech_frontier:Tech Frontier" "university_eco:University Eco" "daily_briefing:Daily Briefing")
    local all_ok=true

    for entry in "${modules[@]}"; do
        local dir_name="${entry%%:*}"
        local display="${entry##*:}"
        local dir="$PROJECT_DIR/data/processed/$dir_name"
        local count=0
        if [[ -d "$dir" ]]; then
            count=$(find "$dir" -name "*.json" -not -name "_*" 2>/dev/null | wc -l | tr -d ' ')
        fi

        if [[ $count -gt 0 ]]; then
            printf "  %-24s %2s files %*s" "$display" "$count" $((W - 46)) ""
            badge_ok
        else
            printf "  %-24s    empty %*s" "$display" $((W - 46)) ""
            badge_warn
            all_ok=false
        fi
        printf "\n"
    done

    if [[ "$all_ok" == "false" ]]; then
        echo ""
        info "Empty modules will be populated when Pipeline runs."
    fi
}

# ── Command Implementations ───────────────────────────────────
cmd_deploy() {
    local total=7
    PRODUCTION=true

    show_header
    section_open "Deploy"

    # [1] Python
    step 1 $total "Python"
    local py_info
    if py_info=$(validate_python); then
        printf "%s  %s\n" "$(badge_ok)" "$py_info"
    else
        printf "%s  %s\n" "$(badge_fail)" "$py_info"
        error "Python >= 3.11 is required"
        section_close
        return 1
    fi

    # [2] Virtual environment
    step 2 $total "Virtual environment"
    if [[ -d "$VENV_DIR" ]]; then
        ensure_venv --create
        printf "%s  %s\n" "$(badge_ok)" ".venv (existing)"
    else
        ensure_venv --create
        printf "%s  %s\n" "$(badge_ok)" ".venv (created)"
    fi

    # [3] Environment file
    step 3 $total "Environment (.env)"
    local env_status
    if env_status=$(validate_env); then
        printf "%s  %s\n" "$(badge_ok)" "$env_status"
    else
        printf "%s  %s\n" "$(badge_fail)" "$env_status"
        section_close
        return 1
    fi
    # Sub-items for important keys
    sub_item "OPENROUTER_API_KEY"
    if check_env_key "OPENROUTER_API_KEY"; then
        badge_ok
    else
        badge_warn
        printf "  not set (LLM enrichment disabled)"
    fi
    printf "\n"
    sub_item "TWITTER_API_KEY" true
    if check_env_key "TWITTER_API_KEY"; then
        badge_ok
    else
        badge_warn
        printf "  not set (Twitter sources disabled)"
    fi
    printf "\n"

    # [4] Dependencies
    step 4 $total "Dependencies"
    local t_start t_end t_dur
    t_start=$(date +%s)
    if install_deps; then
        t_end=$(date +%s)
        t_dur=$((t_end - t_start))
        step 4 $total "Dependencies"
        printf "%s  %ss\n" "$(badge_ok)" "$t_dur"
    else
        step 4 $total "Dependencies"
        printf "%s\n" "$(badge_fail)"
        error "pip install failed — check logs"
        section_close
        return 1
    fi

    # [5] Playwright
    step 5 $total "Playwright Chromium"
    if check_playwright; then
        printf "%s\n" "$(badge_ok)"
    else
        printf "%s  installing...\n" "$(badge_warn)"
        install_playwright
        step 5 $total "Playwright Chromium"
        if check_playwright; then
            printf "%s\n" "$(badge_ok)"
        else
            printf "%s  dynamic crawls unavailable\n" "$(badge_warn)"
        fi
    fi

    # [6] Data directories
    step 6 $total "Data directories"
    ensure_directories
    printf "%s\n" "$(badge_ok)"

    # [7] Service
    step 7 $total "Service"
    if _is_running; then
        local old_pid
        old_pid=$(_get_pid)
        printf "%s  restarting (was PID %s)...\n" "$(badge_warn)" "$old_pid"
        cmd_stop_quiet
        sleep 1
        step 7 $total "Service"
        _launch_uvicorn
        printf "\n"
    else
        _launch_uvicorn
        printf "\n"
    fi

    section_close
    echo ""

    # Status display
    if _is_running; then
        _wait_for_health 0 0 2>/dev/null || true
        sleep 2
        show_service_status
        show_pipeline_status
        show_data_stats
        section_close
        echo ""
        success "Deploy complete"
    else
        error "Service failed to start — check: $LOG_FILE"
    fi

    echo ""
    printf "  ${DIM}Useful commands:${NC}\n"
    printf "    ./deploy.sh status          Show service status\n"
    printf "    ./deploy.sh logs -f         Tail logs in real-time\n"
    printf "    ./deploy.sh restart         Restart service\n"
    printf "    ./deploy.sh stop            Stop service\n"
    echo ""
}

cmd_init() {
    local total=6

    show_header
    section_open "Initialize"

    # [1] Python
    step 1 $total "Python"
    local py_info
    if py_info=$(validate_python); then
        printf "%s  %s\n" "$(badge_ok)" "$py_info"
    else
        printf "%s  %s\n" "$(badge_fail)" "$py_info"
        error "Python >= 3.11 is required"
        section_close
        return 1
    fi

    # [2] Virtual environment
    step 2 $total "Virtual environment"
    if [[ -d "$VENV_DIR" ]]; then
        ensure_venv --create
        printf "%s  %s\n" "$(badge_ok)" ".venv (existing)"
    else
        ensure_venv --create
        printf "%s  %s\n" "$(badge_ok)" ".venv (created)"
    fi

    # [3] Environment file
    step 3 $total "Environment (.env)"
    local env_status
    if env_status=$(validate_env); then
        printf "%s  %s\n" "$(badge_ok)" "$env_status"
    else
        printf "%s  %s\n" "$(badge_fail)" "$env_status"
    fi

    # [4] Dependencies
    step 4 $total "Dependencies"
    local t_start t_end t_dur
    t_start=$(date +%s)
    if install_deps; then
        t_end=$(date +%s)
        t_dur=$((t_end - t_start))
        step 4 $total "Dependencies"
        printf "%s  %ss\n" "$(badge_ok)" "$t_dur"
    else
        step 4 $total "Dependencies"
        printf "%s\n" "$(badge_fail)"
    fi

    # [5] Playwright
    step 5 $total "Playwright Chromium"
    if check_playwright; then
        printf "%s\n" "$(badge_ok)"
    else
        printf "%s  installing...\n" "$(badge_warn)"
        install_playwright
        step 5 $total "Playwright Chromium"
        if check_playwright; then
            printf "%s\n" "$(badge_ok)"
        else
            printf "%s  dynamic crawls unavailable\n" "$(badge_warn)"
        fi
    fi

    # [6] Data directories
    step 6 $total "Data directories"
    ensure_directories
    printf "%s\n" "$(badge_ok)"

    section_close
    echo ""
    success "Initialization complete"
    echo ""
    printf "  ${DIM}Next steps:${NC}\n"
    printf "    1. Edit .env:          vi .env\n"
    printf "    2. Start service:      ./deploy.sh start\n"
    printf "    3. Or full deploy:     ./deploy.sh deploy\n"
    echo ""
}

cmd_start() {
    show_header

    if ! ensure_venv; then
        error "Virtual environment not found. Run: ./deploy.sh init"
        return 1
    fi

    if _is_running; then
        warning "Service already running (PID $(_get_pid))"
        cmd_status_compact
        return 0
    fi

    PRODUCTION=true
    printf "  Starting service (port %s, production mode)...\n" "$PORT"
    _launch_uvicorn
    printf "\n"

    if _is_running; then
        _wait_for_health 0 0 2>/dev/null || true
        sleep 1
        echo ""
        success "Service started"
        printf "  ${DIM}API Docs: http://localhost:%s/docs${NC}\n" "$PORT"
        printf "  ${DIM}Logs:     ./deploy.sh logs -f${NC}\n"
    fi
    echo ""
}

# Stop without output (used by deploy restart)
cmd_stop_quiet() {
    if ! _is_running; then
        local orphans
        orphans=$(_pids_on_port)
        if [[ -n "$orphans" ]]; then
            _free_port
        fi
        return 0
    fi

    local pid
    pid=$(_get_pid)
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do
        sleep 1
        waited=$((waited + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    _free_port 2>/dev/null || true
}

cmd_stop() {
    show_header

    if ! _is_running; then
        local orphans
        orphans=$(_pids_on_port)
        if [[ -n "$orphans" ]]; then
            warning "No PID file, but port $PORT is occupied — cleaning up"
            _free_port
            success "Port freed"
        else
            info "Service is not running"
        fi
        echo ""
        return 0
    fi

    local pid
    pid=$(_get_pid)
    printf "  Stopping service (PID %s) ...\n" "$pid"
    cmd_stop_quiet
    success "Service stopped"
    echo ""
}

cmd_restart() {
    show_header

    if ! ensure_venv; then
        error "Virtual environment not found. Run: ./deploy.sh init"
        return 1
    fi

    PRODUCTION=true

    if _is_running; then
        local pid
        pid=$(_get_pid)
        printf "  Restarting service (PID %s) ...\n" "$pid"
        cmd_stop_quiet
        sleep 1
    else
        printf "  Service not running, starting...\n"
    fi

    _launch_uvicorn
    printf "\n"

    if _is_running; then
        _wait_for_health 0 0 2>/dev/null || true
        sleep 1
        echo ""
        success "Service restarted"
        printf "  ${DIM}API Docs: http://localhost:%s/docs${NC}\n" "$PORT"
    fi
    echo ""
}

cmd_status_compact() {
    if _is_running; then
        local pid etime
        pid=$(_get_pid)
        etime=$(ps -p "$pid" -o etime= 2>/dev/null | xargs || echo "N/A")
        printf "  ${GREEN}●${NC} Running — PID %s, port %s, uptime %s\n" "$pid" "$PORT" "$etime"
    else
        printf "  ${RED}●${NC} Stopped\n"
    fi
}

cmd_status() {
    show_header
    show_service_status

    if _is_running; then
        show_pipeline_status
        show_data_stats
    fi

    section_close

    # Log info
    if [[ -f "$LOG_FILE" ]]; then
        echo ""
        local log_size
        log_size=$(du -h "$LOG_FILE" | cut -f1)
        info "Log file: $LOG_FILE ($log_size)"
    fi
    echo ""
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        warning "Log file not found: $LOG_FILE"
        return 0
    fi

    if [[ "$FOLLOW" == "true" ]]; then
        printf "  ${DIM}Tailing %s (Ctrl+C to stop)${NC}\n\n" "$LOG_FILE"
        tail -n "$TAIL_LINES" -f "$LOG_FILE"
    else
        tail -n "$TAIL_LINES" "$LOG_FILE"
    fi
}

cmd_help() {
    show_header
    printf "  ${BOLD}Usage:${NC}  ./deploy.sh <command> [options]\n"
    printf "\n"
    printf "  ${BOLD}Commands:${NC}\n"
    printf "\n"
    printf "    ${GREEN}deploy${NC}       Full deploy: venv + deps + Playwright + start\n"
    printf "                 (default when no command given)\n"
    printf "    ${GREEN}init${NC}         Initialize environment only (no start)\n"
    printf "    ${GREEN}start${NC}        Start service\n"
    printf "    ${GREEN}stop${NC}         Stop service\n"
    printf "    ${GREEN}restart${NC}      Restart service\n"
    printf "    ${GREEN}status${NC}       Show detailed status\n"
    printf "    ${GREEN}logs${NC}         View service logs\n"
    printf "    ${GREEN}help${NC}         Show this help\n"
    printf "\n"
    printf "  ${BOLD}Options:${NC}\n"
    printf "\n"
    printf "    --port N         Listen port (default: %s)\n" "$PORT"
    printf "    --workers N      Worker count (default: %s)\n" "$WORKERS"
    printf "    --production     Production mode (no auto-reload)\n"
    printf "    --tail N         Log lines to show (default: %s)\n" "$TAIL_LINES"
    printf "    --follow, -f     Follow log output\n"
    printf "\n"
    printf "  ${BOLD}Examples:${NC}\n"
    printf "\n"
    printf "    ./deploy.sh                     Smart deploy (most common)\n"
    printf "    ./deploy.sh start --port 8080   Start on custom port\n"
    printf "    ./deploy.sh logs -f             Tail logs\n"
    printf "    ./deploy.sh status              Check everything\n"
    printf "\n"
}

# ── Argument Parsing ──────────────────────────────────────────
COMMAND="${1:-deploy}"
shift 2>/dev/null || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)       PORT="$2"; shift 2 ;;
        --workers)    WORKERS="$2"; shift 2 ;;
        --tail)       TAIL_LINES="$2"; shift 2 ;;
        --follow|-f)  FOLLOW=true; shift ;;
        --production) PRODUCTION=true; shift ;;
        *) error "Unknown option: $1"; cmd_help; exit 1 ;;
    esac
done

case "$COMMAND" in
    deploy)  cmd_deploy ;;
    init)    cmd_init ;;
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    help|--help|-h) cmd_help ;;
    *)       error "Unknown command: $COMMAND"; cmd_help; exit 1 ;;
esac