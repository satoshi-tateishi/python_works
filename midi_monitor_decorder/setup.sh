#!/bin/bash
# 初回のみ実行: .venv を作成して依存パッケージをインストールする
set -e
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install --quiet -r requirements.txt
echo "セットアップ完了。以下のコマンドで起動できます:"
echo "  .venv/bin/python app.py"
