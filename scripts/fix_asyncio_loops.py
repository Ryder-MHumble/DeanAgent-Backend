#!/usr/bin/env python3
"""批量修复 asyncio.get_event_loop().run_until_complete() 问题

将所有 asyncio.get_event_loop().run_until_complete() 替换为安全的版本
"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# 需要修复的文件
FILES_TO_FIX = [
    "app/services/core/event_service.py",
    "app/services/core/institution_service.py",
    "app/services/core/project_service.py",
]

# 替换模式
OLD_PATTERN = r"asyncio\.get_event_loop\(\)\.run_until_complete\("
NEW_CODE = """# Create new event loop to avoid conflicts with existing loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete("""

def fix_file(file_path: Path):
    """修复单个文件"""
    print(f"修复: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 统计需要替换的次数
    matches = re.findall(OLD_PATTERN, content)
    if not matches:
        print(f"  ⊘ 无需修复")
        return

    print(f"  找到 {len(matches)} 处需要修复")

    # 简单替换：使用 asyncio.run() 代替
    # 这是最安全的方式，会自动处理事件循环
    new_content = re.sub(
        r"asyncio\.get_event_loop\(\)\.run_until_complete\(",
        "asyncio.run(",
        content
    )

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✓ 已修复")

def main():
    print("=" * 70)
    print("批量修复 asyncio 事件循环问题")
    print("=" * 70)
    print()

    for file_rel in FILES_TO_FIX:
        file_path = BASE_DIR / file_rel
        if file_path.exists():
            fix_file(file_path)
        else:
            print(f"✗ 文件不存在: {file_path}")

    print()
    print("=" * 70)
    print("修复完成")
    print("=" * 70)
    print()
    print("下一步:")
    print("  1. 测试本地服务: uvicorn app.main:app --reload")
    print("  2. 测试 API: curl http://localhost:8000/api/v1/scholars/")
    print("  3. 部署到线上: git add . && git commit && git push")

if __name__ == "__main__":
    main()
