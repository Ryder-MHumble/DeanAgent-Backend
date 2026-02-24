#!/usr/bin/env bash
# ------------------------------------------------------------------
# Information Crawler — 服务管理脚本
#
# 用法:
#   ./scripts/service.sh init
#   ./scripts/service.sh start   [--port 8000] [--workers 1] [--production]
#   ./scripts/service.sh stop
#   ./scripts/service.sh restart [--port 8000] [--workers 1] [--production]
#   ./scripts/service.sh status
#   ./scripts/service.sh logs    [--tail 50] [--follow]
# ------------------------------------------------------------------
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_DIR/.service.pid"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/server.log"

# Defaults
PORT=8001
WORKERS=1
TAIL_LINES=50
FOLLOW=false
PRODUCTION=false

# ---- helpers -------------------------------------------------------
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

usage() {
    cat <<'EOF'
Information Crawler 服务管理

用法:
  ./scripts/service.sh <command> [options]

命令:
  init      首次初始化 (安装依赖、Playwright、创建目录、检查配置)
  start     启动后端服务 (uvicorn + scheduler + pipeline)
  stop      停止后端服务
  restart   重启后端服务
  status    查看服务状态
  logs      查看服务日志

start/restart 选项:
  --port N        监听端口 (默认 8000)
  --workers N     worker 数量 (默认 1; APScheduler 不支持多 worker)
  --production    生产模式 (禁用 --reload)

logs 选项:
  --tail N      显示最后 N 行 (默认 50)
  --follow      持续跟踪日志 (等同 tail -f)
EOF
    exit 1
}

_is_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        # stale pid file
        rm -f "$PID_FILE"
    fi
    return 1
}

_get_pid() {
    cat "$PID_FILE" 2>/dev/null || echo ""
}

# Find all PIDs listening on $PORT (handles orphaned uvicorn workers)
_pids_on_port() {
    lsof -ti "tcp:$PORT" 2>/dev/null || true
}

# Kill everything occupying $PORT — the nuclear option for orphan cleanup
_free_port() {
    local pids
    pids=$(_pids_on_port)
    if [[ -z "$pids" ]]; then
        return 0
    fi
    yellow "发现端口 $PORT 被占用 (PIDs: $(echo $pids | tr '\n' ' '))"
    # SIGTERM first
    echo "$pids" | xargs kill 2>/dev/null || true
    sleep 2
    # Check again — SIGKILL survivors
    pids=$(_pids_on_port)
    if [[ -n "$pids" ]]; then
        yellow "进程未退出, 强制终止..."
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
    # Final check
    pids=$(_pids_on_port)
    if [[ -n "$pids" ]]; then
        red "无法释放端口 $PORT — 请手动检查: lsof -i :$PORT"
        return 1
    fi
    green "端口 $PORT 已释放"
}

_wait_for_health() {
    local max_wait=30
    local waited=0
    echo "  等待健康检查..."
    while [[ $waited -lt $max_wait ]]; do
        if curl -sf "http://localhost:$PORT/api/v1/health/" >/dev/null 2>&1; then
            green "  健康检查通过!"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    yellow "  健康检查超时 (${max_wait}s) — 服务可能仍在初始化"
}

# ---- commands ------------------------------------------------------
cmd_init() {
    green "=== Information Crawler 初始化 ==="
    echo ""

    # 1. Check Python version
    local py_version
    py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    echo "Python 版本: $py_version"
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        green "  Python >= 3.11 OK"
    else
        red "  需要 Python >= 3.11"
        return 1
    fi

    # 2. Install dependencies
    echo ""
    green "安装 Python 依赖..."
    cd "$PROJECT_DIR"
    pip install -e ".[dev]" || { red "依赖安装失败"; return 1; }

    # 3. Install Playwright browser
    echo ""
    green "安装 Playwright Chromium..."
    playwright install chromium --with-deps 2>/dev/null || playwright install chromium || {
        yellow "Playwright 安装失败 — dynamic 爬虫将不可用"
    }

    # 4. Create data directories
    echo ""
    green "创建数据目录..."
    mkdir -p "$PROJECT_DIR/data/raw"
    mkdir -p "$PROJECT_DIR/data/processed/policy_intel"
    mkdir -p "$PROJECT_DIR/data/processed/personnel_intel"
    mkdir -p "$PROJECT_DIR/logs"
    green "  目录创建完成"

    # 5. Check .env file
    echo ""
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        yellow ".env 文件不存在"
        echo "  请创建 .env 文件并配置 DATABASE_URL:"
        echo "  cp .env.example .env && vi .env"
    else
        green ".env 文件存在"
        if grep -q "DATABASE_URL" "$PROJECT_DIR/.env" && ! grep -q "DATABASE_URL=postgresql+asyncpg://postgres:password@" "$PROJECT_DIR/.env"; then
            green "  DATABASE_URL: 已配置"
        else
            yellow "  DATABASE_URL: 使用默认值 (请修改为实际数据库地址)"
        fi
        if grep -q "OPENROUTER_API_KEY=.\+" "$PROJECT_DIR/.env"; then
            green "  OPENROUTER_API_KEY: 已配置 (LLM 富化将自动启用)"
        else
            yellow "  OPENROUTER_API_KEY: 未配置 (LLM 富化将跳过)"
        fi
        if grep -q "TWITTER_API_KEY=.\+" "$PROJECT_DIR/.env"; then
            green "  TWITTER_API_KEY: 已配置"
        else
            yellow "  TWITTER_API_KEY: 未配置 (Twitter 信源将不可用)"
        fi
    fi

    echo ""
    green "=== 初始化完成 ==="
    echo ""
    echo "下一步:"
    echo "  1. 确保 .env 中配置了正确的 DATABASE_URL"
    echo "  2. 启动服务: ./scripts/service.sh start"
    echo "  3. 查看文档: http://localhost:8000/docs"
    echo "  4. 首次启动会自动触发全量数据采集 Pipeline"
}

cmd_start() {
    if _is_running; then
        yellow "服务已在运行 (PID $(_get_pid)), 端口 $PORT"
        return 0
    fi

    # Always ensure port is free before starting (kills orphaned workers)
    _free_port || return 1
    # Clean stale PID file
    rm -f "$PID_FILE"

    mkdir -p "$LOG_DIR"

    local extra_args=()
    if [[ "$PRODUCTION" == "true" ]]; then
        # Production: no reload, keep workers=1 (APScheduler limitation)
        green "生产模式: port=$PORT workers=$WORKERS (no-reload)"
    elif [[ "$WORKERS" -eq 1 ]]; then
        extra_args+=(--reload)
        green "开发模式: port=$PORT workers=$WORKERS (reload)"
    else
        green "启动服务: port=$PORT workers=$WORKERS"
    fi

    cd "$PROJECT_DIR"
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --workers "$WORKERS" \
        "${extra_args[@]}" \
        >> "$LOG_FILE" 2>&1 &

    local pid=$!
    echo "$pid" > "$PID_FILE"

    # Wait briefly to check it started
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        green "服务已启动 (PID $pid)"
        echo "  API:  http://localhost:$PORT/docs"
        echo "  日志: $LOG_FILE"

        # Health check
        _wait_for_health
    else
        red "启动失败, 查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

cmd_stop() {
    if ! _is_running; then
        # Even without PID file, port might still be occupied by orphans
        local orphans
        orphans=$(_pids_on_port)
        if [[ -n "$orphans" ]]; then
            yellow "未找到 PID 文件, 但端口 $PORT 被占用 — 清理孤儿进程"
            _free_port
        else
            yellow "服务未运行"
        fi
        return 0
    fi

    local pid
    pid=$(_get_pid)
    green "停止服务 (PID $pid) ..."

    # Kill the entire process group (catches uvicorn workers + reload watcher)
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do
        sleep 1
        waited=$((waited + 1))
    done

    # Force kill process group if still alive
    if kill -0 "$pid" 2>/dev/null; then
        yellow "进程组未响应 SIGTERM, 发送 SIGKILL ..."
        kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"

    # Final safety: clean up any remaining port occupants
    _free_port 2>/dev/null || true

    green "服务已停止"
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    if _is_running; then
        local pid
        pid=$(_get_pid)
        green "服务运行中 (PID $pid)"

        # Show port info
        if command -v lsof &>/dev/null; then
            echo ""
            echo "监听端口:"
            lsof -i -P -n -p "$pid" 2>/dev/null | grep LISTEN || echo "  (未检测到监听端口)"
        fi

        # Show resource usage
        echo ""
        echo "资源占用:"
        ps -p "$pid" -o pid,ppid,%cpu,%mem,rss,etime,command 2>/dev/null | head -2

        # Show health endpoint
        echo ""
        echo "健康状态:"
        curl -sf "http://localhost:$PORT/api/v1/health/" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (无法连接)"

        # Show pipeline status
        echo ""
        echo "Pipeline 状态:"
        curl -sf "http://localhost:$PORT/api/v1/health/pipeline-status" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (无法获取)"
    else
        red "服务未运行"
    fi

    # Show log file info
    if [[ -f "$LOG_FILE" ]]; then
        echo ""
        echo "日志文件: $LOG_FILE ($(du -h "$LOG_FILE" | cut -f1))"
    fi
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        yellow "日志文件不存在: $LOG_FILE"
        return 0
    fi

    if [[ "$FOLLOW" == "true" ]]; then
        tail -n "$TAIL_LINES" -f "$LOG_FILE"
    else
        tail -n "$TAIL_LINES" "$LOG_FILE"
    fi
}

# ---- argument parsing ----------------------------------------------
COMMAND="${1:-}"
shift || true

if [[ -z "$COMMAND" ]]; then
    usage
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)       PORT="$2"; shift 2 ;;
        --workers)    WORKERS="$2"; shift 2 ;;
        --tail)       TAIL_LINES="$2"; shift 2 ;;
        --follow|-f)  FOLLOW=true; shift ;;
        --production) PRODUCTION=true; shift ;;
        *) red "未知参数: $1"; usage ;;
    esac
done

case "$COMMAND" in
    init)    cmd_init ;;
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    *)       red "未知命令: $COMMAND"; usage ;;
esac
