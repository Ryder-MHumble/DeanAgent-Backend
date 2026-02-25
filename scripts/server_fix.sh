#!/usr/bin/env bash
# ------------------------------------------------------------------
# 服务器一键修复脚本
#
# 修复内容:
#   1. 清理 .env 文件中的垃圾内容 (exit()/q)
#   2. 安装 Playwright Chromium 浏览器
#   3. 创建缺失的 data 目录
#   4. 以生产模式重启服务
#   5. 等待 Pipeline 自动触发并检查结果
#
# 用法:
#   chmod +x scripts/server_fix.sh
#   ./scripts/server_fix.sh
# ------------------------------------------------------------------
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

echo ""
blue "============================================"
blue "  Information Crawler — 服务器修复脚本"
blue "============================================"
echo ""

# ------------------------------------------------------------------
# Step 1: 修复 .env 文件
# ------------------------------------------------------------------
green "[1/5] 检查并修复 .env 文件..."

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    yellow "  .env 文件不存在，从 .env.example 创建..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    green "  已创建 .env (请稍后编辑填入 API keys)"
else
    # 移除常见的垃圾行: exit(), q, :q, :wq 等
    if grep -qE '^(exit\(\)|q|:q|:wq|:x)\s*$' "$PROJECT_DIR/.env" 2>/dev/null; then
        yellow "  发现 .env 中的垃圾内容，正在清理..."
        # macOS 和 Linux 兼容的 sed
        if [[ "$(uname)" == "Darwin" ]]; then
            sed -i '' '/^exit()$/d; /^q$/d; /^:q$/d; /^:wq$/d; /^:x$/d' "$PROJECT_DIR/.env"
        else
            sed -i '/^exit()$/d; /^q$/d; /^:q$/d; /^:wq$/d; /^:x$/d' "$PROJECT_DIR/.env"
        fi
        green "  .env 已清理"
    else
        green "  .env 文件正常"
    fi
fi

echo ""

# ------------------------------------------------------------------
# Step 2: 安装 Playwright
# ------------------------------------------------------------------
green "[2/5] 检查并安装 Playwright..."

if python3 -c "import playwright" 2>/dev/null; then
    green "  playwright Python 包已安装"
else
    yellow "  安装 playwright Python 包..."
    pip install playwright
fi

# 检查 Chromium 是否已安装
if python3 -c "
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
try:
    b = pw.chromium.launch(headless=True)
    b.close()
    print('ok')
except Exception as e:
    print(f'fail: {e}')
    exit(1)
finally:
    pw.stop()
" 2>/dev/null; then
    green "  Playwright Chromium 浏览器已安装"
else
    yellow "  安装 Playwright Chromium 浏览器..."
    playwright install chromium --with-deps 2>/dev/null || playwright install chromium || {
        red "  Playwright 安装失败 — dynamic 类型爬虫将不可用"
        yellow "  可手动运行: playwright install chromium --with-deps"
    }
fi

echo ""

# ------------------------------------------------------------------
# Step 3: 创建缺失的数据目录
# ------------------------------------------------------------------
green "[3/5] 确保数据目录完整..."

for dir in \
    "data/raw" \
    "data/processed/policy_intel" \
    "data/processed/personnel_intel" \
    "data/processed/tech_frontier" \
    "data/processed/university_eco" \
    "data/processed/daily_briefing" \
    "data/state" \
    "data/logs" \
    "logs"
do
    mkdir -p "$PROJECT_DIR/$dir"
done
green "  数据目录已就绪"

echo ""

# ------------------------------------------------------------------
# Step 4: 以生产模式重启服务
# ------------------------------------------------------------------
green "[4/5] 以生产模式重启服务..."

./scripts/service.sh stop 2>/dev/null || true
sleep 2
./scripts/service.sh start --production

echo ""

# ------------------------------------------------------------------
# Step 5: 检查服务状态
# ------------------------------------------------------------------
green "[5/5] 检查服务状态..."

sleep 5  # 等待服务完全启动

echo ""
echo "健康检查:"
curl -sf "http://localhost:8001/api/v1/health/" 2>/dev/null | python3 -m json.tool 2>/dev/null || yellow "  (健康检查未响应，服务可能仍在启动中)"

echo ""
echo "Pipeline 状态:"
curl -sf "http://localhost:8001/api/v1/health/pipeline-status" 2>/dev/null | python3 -m json.tool 2>/dev/null || yellow "  (无法获取 pipeline 状态)"

echo ""
echo "已处理数据:"
for dir in policy_intel personnel_intel tech_frontier university_eco daily_briefing; do
    count=$(find "$PROJECT_DIR/data/processed/$dir" -name "*.json" -not -name "_*" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$count" -gt 0 ]]; then
        green "  $dir: ${count} 个文件"
    else
        yellow "  $dir: 空 (等待 Pipeline 执行)"
    fi
done

echo ""
blue "============================================"
blue "  修复完成!"
blue "============================================"
echo ""
echo "如果 Pipeline 尚未运行，它将在启动时自动触发。"
echo "你也可以手动触发:"
echo "  curl -X POST http://localhost:8001/api/v1/health/pipeline-trigger"
echo ""
echo "跟踪日志:"
echo "  ./scripts/service.sh logs --follow"
echo ""
