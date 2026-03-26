#!/usr/bin/env python3
"""
MIDI MSC Monitor macOS アプリビルドスクリプト

使い方:
  .venv/bin/python build_app.py               # arm64 と x86_64 を順番にビルド
  .venv/bin/python build_app.py --arch arm64  # arm64 (.venv) のみ
  .venv/bin/python build_app.py --arch x86_64 # x86_64 (.venv_x86) のみ
  .venv/bin/python build_app.py --arch x86_64_1013_py312
      # macOS 10.13.6 向け x86_64 / Python 3.12 (.venv_x86_1013_py312) のみ
"""

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
DIST_DIR = CURRENT_DIR / "dist"
WORK_DIR = CURRENT_DIR / "build"

with open(CURRENT_DIR / "config.json", encoding="utf-8") as _f:
    _config = json.load(_f)

APP_NAME = _config["app_name"]
BUNDLE_ID = _config["bundle_id"]
DEVELOPER = _config.get("developer", "")
UPDATED = _config.get("updated", "")

# アーキテクチャ別の設定
ARCH_CONFIGS = {
    "arm64": {
        "venv": CURRENT_DIR / ".venv",
        "target_arch": "arm64",
        "app_name": f"{APP_NAME}_arm64",
        "setup_hint": "bash setup.sh",
        "extra_env": {},
    },
    "x86_64": {
        "venv": CURRENT_DIR / ".venv_x86",
        "target_arch": "x86_64",
        "app_name": f"{APP_NAME}_x86_64",
        "setup_hint": "bash setup.sh --x86",
        "extra_env": {},
    },
    "x86_64_1013_py312": {
        "venv": CURRENT_DIR / ".venv_x86_1013_py312",
        "target_arch": "x86_64",
        "app_name": f"{APP_NAME}_x86_64_1013_py312",
        "setup_hint": "bash setup.sh --x86-1013-py312",
        "extra_env": {},
    },
}


def get_app_version():
    return _config["version"]


def run_ruff():
    """Ruff チェックは arm64 の .venv で実行（共通）"""
    print("=== Ruff チェック ===")
    ruff = CURRENT_DIR / ".venv" / "bin" / "ruff"
    subprocess.run(
        [str(ruff), "check", "decoder.py", "midi_receiver.py", "persistence.py", "app.py"],
        cwd=CURRENT_DIR,
        check=True,
    )
    subprocess.run(
        [
            str(ruff),
            "format",
            "--check",
            "decoder.py",
            "midi_receiver.py",
            "persistence.py",
            "app.py",
        ],
        cwd=CURRENT_DIR,
        check=True,
    )
    print("OK\n")


def clear_previous_builds(app_name: str):
    work_dir = WORK_DIR / app_name
    dist_app = DIST_DIR / f"{app_name}.app"
    for path in [work_dir, dist_app]:
        if path.exists():
            print(f"Cleaning {path}...")
            for i in range(5):
                try:
                    shutil.rmtree(path)
                    break
                except OSError:
                    if i < 4:
                        time.sleep(0.5)
                    else:
                        temp = path.with_name(f"{path.name}_old_{int(time.time())}")
                        os.rename(path, temp)
                        shutil.rmtree(temp, ignore_errors=True)


def fix_plist(app_name: str):
    app_path = DIST_DIR / f"{app_name}.app"
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.exists():
        return

    version = get_app_version()
    with open(plist_path, "rb") as f:
        pl = plistlib.load(f)

    pl["LSUIElement"] = False
    pl["LSBackgroundOnly"] = False
    pl["CFBundleName"] = APP_NAME
    pl["CFBundleDisplayName"] = APP_NAME
    pl["CFBundlePackageType"] = "APPL"
    pl["CFBundleShortVersionString"] = version
    pl["CFBundleVersion"] = version
    pl["NSHumanReadableCopyright"] = f"Developer: {DEVELOPER}\nUpdated: {UPDATED}"

    with open(plist_path, "wb") as f:
        plistlib.dump(pl, f)

    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework"
        "/Frameworks/LaunchServices.framework/Support/lsregister"
    )
    if os.path.exists(lsregister):
        subprocess.run([lsregister, "-f", str(app_path)])


def build_arch(arch: str) -> bool:
    cfg = ARCH_CONFIGS[arch]
    venv: Path = cfg["venv"]
    target_arch: str = cfg["target_arch"]
    app_name: str = cfg["app_name"]

    if not venv.exists():
        print(f"⚠️  {arch} 用の venv が見つかりません ({venv})")
        hint = cfg["setup_hint"]
        print(f"   先に '{hint}' を実行してください。\n")
        return False

    print(f"--- {app_name} ビルド開始 ({arch}) ---\n")

    pyinstaller = venv / "bin" / "pyinstaller"
    clear_previous_builds(app_name)

    sep = ":" if os.name == "posix" else ";"
    work_dir = WORK_DIR / app_name
    args = [
        str(CURRENT_DIR / "app.py"),
        f"--name={app_name}",
        "--noconfirm",
        "--windowed",
        "--clean",
        f"--target-arch={target_arch}",
        f"--distpath={DIST_DIR}",
        f"--workpath={work_dir}",
        f"--specpath={work_dir}",
        f"--osx-bundle-identifier={BUNDLE_ID}",
        f"--add-data={CURRENT_DIR / 'decoder.py'}{sep}.",
        f"--add-data={CURRENT_DIR / 'midi_receiver.py'}{sep}.",
        f"--add-data={CURRENT_DIR / 'persistence.py'}{sep}.",
        f"--add-data={CURRENT_DIR / 'config.json'}{sep}.",
        "--hidden-import=flask",
        "--hidden-import=werkzeug",
        "--hidden-import=webview",
        "--hidden-import=objc",
        "--hidden-import=Foundation",
        "--hidden-import=AppKit",
        "--hidden-import=WebKit",
        "--hidden-import=rtmidi",
    ]

    try:
        # アーキテクチャ専用 venv の pyinstaller をサブプロセスで実行
        # x86_64 は Rosetta 2 経由で arch -x86_64 を付けて呼ぶ
        env = os.environ.copy()
        env.update(cfg.get("extra_env", {}))
        if arch.startswith("x86_64"):
            cmd = ["arch", "-x86_64", str(pyinstaller)]
        else:
            cmd = [str(pyinstaller)]
        subprocess.run(cmd + args, cwd=CURRENT_DIR, check=True, env=env)
    except Exception:
        traceback.print_exc()
        print(f"\n❌ {arch} ビルドエラー\n")
        return False

    fix_plist(app_name)
    print(f"\n✅ {arch} ビルド完了: {DIST_DIR}/{app_name}.app\n")
    return True


def build(archs: list[str]):
    run_ruff()
    results = {}
    for arch in archs:
        results[arch] = build_arch(arch)

    print("=== ビルド結果 ===")
    for arch, ok in results.items():
        mark = "✅" if ok else "❌"
        print(f"  {mark} {arch}: {ARCH_CONFIGS[arch]['app_name']}.app")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MSC_MTC_Viewer ビルドスクリプト")
    parser.add_argument(
        "--arch",
        choices=["arm64", "x86_64", "x86_64_1013_py312"],
        default=None,
        help="ビルド対象アーキテクチャ（省略時は両方）",
    )
    args = parser.parse_args()

    archs = [args.arch] if args.arch else ["arm64", "x86_64"]
    build(archs)
