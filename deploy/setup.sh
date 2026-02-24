#!/usr/bin/env bash
# ------------------------------------------------------------------
# Information Crawler — 服务器部署脚本
#
# 将 systemd unit 文件安装到系统并启用服务。
#
# 用法:
#   sudo bash deploy/setup.sh
#
# 前提:
#   1. 项目已部署到 /opt/information-crawler
#   2. 已创建 crawler 用户: sudo useradd -r -s /bin/false crawler
#   3. Python venv 已创建: python3 -m venv /opt/information-crawler/.venv
#   4. 依赖已安装: .venv/bin/pip install -e .
#   5. Playwright 已安装: .venv/bin/playwright install chromium --with-deps
#   6. .env 已配置
# ------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/information-crawler"
SERVICE_FILE="information-crawler.service"

# Check root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

# Check install directory
if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "Error: Install directory not found: $INSTALL_DIR"
    echo "Please deploy the project to $INSTALL_DIR first."
    exit 1
fi

# Copy unit file
echo "Copying systemd unit file..."
cp "$SCRIPT_DIR/$SERVICE_FILE" /etc/systemd/system/

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service (start on boot)
echo "Enabling service..."
systemctl enable information-crawler

echo ""
echo "=== 部署完成 ==="
echo ""
echo "管理命令:"
echo "  sudo systemctl start information-crawler     # 启动"
echo "  sudo systemctl stop information-crawler      # 停止"
echo "  sudo systemctl restart information-crawler   # 重启"
echo "  sudo systemctl status information-crawler    # 状态"
echo "  sudo journalctl -u information-crawler -f    # 日志"
echo ""
echo "健康检查:"
echo "  curl http://localhost:8000/api/v1/health/"
echo "  curl http://localhost:8000/api/v1/health/pipeline-status"
