#!/bin/bash
# 初回のみ実行: .venv を作成して依存パッケージをインストールする
set -e
cd "$(dirname "$0")"

PYTHON39_ORG="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"

if [ -f "$PYTHON39_ORG" ]; then
  # universal2 ビルド用: python.org 版 Python を使用
  "$PYTHON39_ORG" -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
  # arm64 専用 wheel が入るパッケージをソースから universal2 としてビルド
  ARCHFLAGS="-arch x86_64 -arch arm64" \
    .venv/bin/pip install --quiet --no-binary markupsafe markupsafe==3.0.3 --force-reinstall
else
  # フォールバック: システムの python3（arm64 専用ビルドになる）
  echo "警告: python.org 版 Python 3.13 が見つかりません。arm64 専用でセットアップします。"
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi

echo "セットアップ完了。以下のコマンドで起動できます:"
echo "  .venv/bin/python app.py"
