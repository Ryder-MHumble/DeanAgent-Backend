#!/bin/bash
# 本地开发快速启停脚本

PORT=8001
APP="app.main:app"
VENV=".venv/bin/activate"

W='\033[1;97m'   # bright white
C='\033[1;36m'   # bright cyan
G='\033[0;32m'   # green
Y='\033[1;33m'   # yellow
R='\033[0;31m'   # red
D='\033[2;37m'   # dim
NC='\033[0m'

show_banner() {
  echo
  echo -e "  ${W}███████  ██   ██  ███████  ███████  ██     ${NC}"
  echo -e "  ${W}  ███    ███  ██    ███    ██       ██     ${NC}"
  echo -e "  ${C}  ███    ████ ██    ███    █████    ██     ${NC}"
  echo -e "  ${C}  ███    ██ ████    ███    ██       ██     ${NC}"
  echo -e "  ${C}███████  ██   ██    ███    ███████  ███████${NC}"
  echo -e "  ${D}─────────────────────────────────────────────${NC}"
  echo -e "  ${D}AI 信息监测平台  ·  中关村人工智能研究院  ·  v1.0${NC}"
  echo -e "  ${D}─────────────────────────────────────────────${NC}"
  echo
}

kill_port() {
  local pids
  pids=$(lsof -ti :$PORT 2>/dev/null)
  if [ -n "$pids" ]; then
    echo -e "  ${Y}关闭端口 $PORT 占用进程 (PID: $pids)...${NC}"
    kill $pids 2>/dev/null
    sleep 1
    pids=$(lsof -ti :$PORT 2>/dev/null)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null
  fi
}

case "${1:-start}" in
  start)
    show_banner
    kill_port
    if [ -f "$VENV" ]; then
      source "$VENV"
    else
      echo -e "  ${Y}未找到 .venv，使用系统 Python${NC}"
    fi
    echo -e "  ${G}▶  服务地址  http://127.0.0.1:${PORT}${NC}"
    echo -e "  ${D}   API 文档  http://127.0.0.1:${PORT}/docs${NC}"
    echo
    uvicorn $APP --reload --port $PORT
    ;;
  stop)
    pids=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$pids" ]; then
      kill $pids 2>/dev/null
      echo -e "${G}已停止 (PID: $pids)${NC}"
    else
      echo "服务未运行"
    fi
    ;;
  status)
    pids=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$pids" ]; then
      echo -e "${G}运行中 (PID: $pids) → http://127.0.0.1:$PORT${NC}"
    else
      echo -e "${R}未运行${NC}"
    fi
    ;;
  *)
    echo "用法: ./dev.sh [start|stop|status]"
    ;;
esac
