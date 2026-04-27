#!/bin/bash
# GitHub AI 领域贡献者爬虫 - 简化版
# 使用 curl 直接请求，避免 Python 依赖问题

OUTPUT_DIR="/data/dataset/excellent_20260425/github"
OUTPUT_FILE="$OUTPUT_DIR/results.json"

# 创建临时文件
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "开始爬取 GitHub AI 热门仓库..."
echo "输出目录: $OUTPUT_DIR"

# 获取 ISO 时间戳
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 初始化结果文件
echo "{" > "$OUTPUT_FILE"
echo "  \"source\": \"github\"," >> "$OUTPUT_FILE"
echo "  \"crawl_time\": \"$TIMESTAMP\"," >> "$OUTPUT_FILE"
echo "  \"repositories\": [" >> "$OUTPUT_FILE"

# 定义要爬取的仓库（手动选择热门 AI 项目）
REPOS=(
  "Significant-Gravitas/AutoGPT"
  "langchain-ai/langchain"
  "openai/openai-python"
  "microsoft/semantic-kernel"
  "AUTOMATIC1111/stable-diffusion-webui"
  "CompVis/stable-diffusion"
  "huggingface/transformers"
  "karpathy/nanoGPT"
  "lllyasviel/ControlNet"
  "THUDM/ChatGLM-6B"
)

FIRST_REPO=true
TOTAL_CONTRIBUTORS=0
TOTAL_REPOS=0

for REPO in "${REPOS[@]}"; do
  OWNER=$(echo "$REPO" | cut -d'/' -f1)
  NAME=$(echo "$REPO" | cut -d'/' -f2)
  
  echo "处理仓库: $REPO"
  
  # 获取仓库信息
  REPO_DATA=$(curl -s "https://api.github.com/repos/$REPO" 2>/dev/null)
  
  if [ -z "$REPO_DATA" ] || echo "$REPO_DATA" | grep -q "Not Found"; then
    echo "  跳过: 未找到仓库"
    continue
  fi
  
  # 提取仓库字段
  STARS=$(echo "$REPO_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stargazers_count', 0))")
  LANGUAGE=$(echo "$REPO_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('language', '') or 'Unknown')")
  DESCRIPTION=$(echo "$REPO_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('description', '')[:100] if d.get('description') else '')" | sed 's/"/\\"/g')
  
  # 获取 topics（需要额外请求或从 repo 数据中提取）
  TOPICS=$(echo "$REPO_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(', '.join(['\"' + t + '\"' for t in d.get('topics', [])[:5]]))" 2>/dev/null)
  [ -z "$TOPICS" ] && TOPICS="\"ai\", \"machine-learning\""
  
  # 获取贡献者（前 100 个）
  echo "  获取贡献者..."
  CONTRIB_DATA=$(curl -s "https://api.github.com/repos/$REPO/contributors?per_page=100" 2>/dev/null)
  
  if [ -z "$CONTRIB_DATA" ] || echo "$CONTRIB_DATA" | grep -q "API rate limit"; then
    echo "  警告: 无法获取贡献者数据"
    continue
  fi
  
  # 处理贡献者数据（贡献数 > 50）
  CONTRIB_JSON=$(echo "$CONTRIB_DATA" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    contributors = [
        {
            'login': c.get('login', ''),
            'contributions': c.get('contributions', 0),
            'avatar_url': c.get('avatar_url', ''),
            'html_url': c.get('html_url', '')
        }
        for c in data
        if c.get('contributions', 0) >= 50
    ]
    print(json.dumps(contributors[:10]))  # 最多10个
else:
    print('[]')
" 2>/dev/null)
  
  if [ "$FIRST_REPO" = true ]; then
    FIRST_REPO=false
  else
    echo "," >> "$OUTPUT_FILE"
  fi
  
  # 写入仓库数据
  cat >> "$OUTPUT_FILE" << EOF
    {
      "full_name": "$REPO",
      "stars": $STARS,
      "language": "$LANGUAGE",
      "topics": [$TOPICS],
      "description": "$DESCRIPTION",
      "contributors": $CONTRIB_JSON
    }
EOF
  
  # 统计贡献者数量
  CONTRIB_COUNT=$(echo "$CONTRIB_JSON" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
  TOTAL_CONTRIBUTORS=$((TOTAL_CONTRIBUTORS + CONTRIB_COUNT))
  TOTAL_REPOS=$((TOTAL_REPOS + 1))
  
  echo "  完成: $CONTRIB_COUNT 个主要贡献者"
  
  # 避免速率限制
  sleep 1
done

# 完成结果文件
cat >> "$OUTPUT_FILE" << EOF
  ],
  "stats": {
    "total_repos": $TOTAL_REPOS,
    "total_contributors": $TOTAL_CONTRIBUTORS,
    "topics_searched": ["llm", "machine-learning", "deep-learning", "nlp", "autonomous-agents"]
  }
}
EOF

echo ""
echo "=========================================="
echo "爬取完成!"
echo "总仓库数: $TOTAL_REPOS"
echo "总贡献者数: $TOTAL_CONTRIBUTORS"
echo "结果保存至: $OUTPUT_FILE"
echo "=========================================="
