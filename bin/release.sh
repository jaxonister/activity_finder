#!/usr/bin/env bash
# 获取当前脚本的绝对路径，并回到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "当前目录：$(pwd)"

export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"


# 如果 dist 目录存在并且非空，则删除其中所有文件
if [ -d dist ] && [ "$(ls -A dist)" ]; then
  echo "清理 dist 目录..."
  rm dist/*
fi

# 构建包
echo "开始构建..."
pip install -q twine build
python -m build
twine upload -r pypi dist/*
