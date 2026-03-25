#!/bin/bash
# 使い方:
#   bash setup.sh          → .venv (arm64) をセットアップ
#   bash setup.sh --x86    → .venv_x86 (x86_64) をセットアップ
#   bash setup.sh --all    → 両方をセットアップ
set -e
cd "$(dirname "$0")"

PYTHON313_ORG="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"

# 引数解析
BUILD_ARM64=false
BUILD_X86=false
case "${1:-}" in
  --x86)  BUILD_X86=true ;;
  --all)  BUILD_ARM64=true; BUILD_X86=true ;;
  "")     BUILD_ARM64=true ;;
  *)      echo "使い方: bash setup.sh [--x86|--all]"; exit 1 ;;
esac

if [ ! -f "$PYTHON313_ORG" ]; then
  echo "エラー: python.org 版 Python 3.13 が見つかりません: $PYTHON313_ORG"
  exit 1
fi

# ---- arm64 (.venv) ----
if $BUILD_ARM64; then
  echo "=== arm64 環境 (.venv) をセットアップ中 ==="
  "$PYTHON313_ORG" -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
  # markupsafe は arm64 専用 wheel が配布されているためソースから universal2 でビルド
  ARCHFLAGS="-arch x86_64 -arch arm64" \
    .venv/bin/pip install --quiet --no-binary markupsafe markupsafe==3.0.3 --force-reinstall
  echo "arm64 環境セットアップ完了"
fi

# ---- x86_64 (.venv_x86) ----
if $BUILD_X86; then
  echo "=== x86_64 環境 (.venv_x86) をセットアップ中 (Rosetta 2) ==="
  arch -x86_64 "$PYTHON313_ORG" -m venv .venv_x86
  arch -x86_64 .venv_x86/bin/pip install --quiet -r requirements.txt
  echo "x86_64 環境セットアップ完了"
fi

echo ""
echo "セットアップ完了。以下のコマンドで起動できます:"
echo "  .venv/bin/python app.py"
