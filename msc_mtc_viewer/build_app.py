#!/usr/bin/env python3
"""
MIDI MSC Monitor macOS アプリビルドスクリプト
Usage: .venv/bin/python build_app.py
"""

import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time

import PyInstaller.__main__

CURRENT_DIR = Path(__file__).resolve().parent
DIST_DIR = CURRENT_DIR / "dist"
WORK_DIR = CURRENT_DIR / "build"

with open(CURRENT_DIR / "config.json", encoding="utf-8") as _f:
    _config = json.load(_f)

APP_NAME = _config["app_name"]
BUNDLE_ID = _config["bundle_id"]
DEVELOPER = _config.get("developer", "")


def get_app_version():
    return _config["version"]


def run_ruff():
    print("=== Ruff チェック ===")
    ruff = CURRENT_DIR / ".venv" / "bin" / "ruff"
    subprocess.run(
        [str(ruff), "check", "decoder.py", "midi_receiver.py", "persistence.py", "app.py"],
        cwd=CURRENT_DIR,
        check=True,
    )
    subprocess.run(
        [str(ruff), "format", "--check", "decoder.py", "midi_receiver.py", "persistence.py", "app.py"],
        cwd=CURRENT_DIR,
        check=True,
    )
    print("OK\n")


def clear_previous_builds():
    for path in [DIST_DIR, WORK_DIR]:
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


def fix_plist():
    app_path = DIST_DIR / f"{APP_NAME}.app"
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
    pl["NSHumanReadableCopyright"] = f"Developer: {DEVELOPER}"

    with open(plist_path, "wb") as f:
        plistlib.dump(pl, f)

    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework"
        "/Frameworks/LaunchServices.framework/Support/lsregister"
    )
    if os.path.exists(lsregister):
        subprocess.run([lsregister, "-f", str(app_path)])


def build():
    print(f"--- {APP_NAME} ビルド開始 ---\n")
    run_ruff()
    clear_previous_builds()

    sep = ":" if os.name == "posix" else ";"
    args = [
        str(CURRENT_DIR / "app.py"),
        f"--name={APP_NAME}",
        "--noconfirm",
        "--windowed",
        "--clean",
        "--target-arch=universal2",
        f"--distpath={DIST_DIR}",
        f"--workpath={WORK_DIR}",
        f"--specpath={WORK_DIR}",
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
        PyInstaller.__main__.run(args)
        fix_plist()
        print(f"\n✅ ビルド完了！\n{DIST_DIR}/{APP_NAME}.app")
    except Exception as e:
        print(f"\n❌ ビルドエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build()
