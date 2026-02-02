import PyInstaller.__main__
import os
import shutil
from pathlib import Path
import sys
import plistlib
import subprocess
import time

# --- 設定 ---
CURRENT_DIR = Path(__file__).resolve().parent
APP_ROOT = CURRENT_DIR.parent
DIST_DIR = APP_ROOT.parent / "dist"
WORK_DIR = APP_ROOT.parent / "build"
APP_NAME = "RF_Unyo_System"

def clear_previous_builds():
    """古いビルドファイルを削除してクリーンな状態にする (macOSのリトライ対策付き) """
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
                        continue
                    else:
                        try:
                            temp_path = path.with_name(f"{path.name}_old_{int(time.time())}")
                            os.rename(path, temp_path)
                            shutil.rmtree(temp_path, ignore_errors=True)
                            break
                        except Exception as e:
                            print(f"❌ エラー: {path} を削除できませんでした。\n   理由: {e}")
                            sys.exit(1)

def fix_plist_and_register():
    """Info.plistを修正し、macOSのLaunch Servicesに再登録する"""
    app_path = DIST_DIR / f"{APP_NAME}.app"
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.exists(): return

    with open(plist_path, 'rb') as f: pl = plistlib.load(f)
    pl['LSUIElement'] = False
    pl['LSBackgroundOnly'] = False
    pl['CFBundleName'] = APP_NAME
    pl['CFBundleDisplayName'] = APP_NAME
    pl['CFBundlePackageType'] = 'APPL'
    with open(plist_path, 'wb') as f: plistlib.dump(pl, f)
    
    lsregister_path = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    if os.path.exists(lsregister_path):
        subprocess.run([lsregister_path, "-f", str(app_path)])
    else:
        subprocess.run(["touch", str(app_path)])

def build():
    print("--- macOSアプリケーションビルド開始 (整理版) ---")
    clear_previous_builds()
    
    SCRIPT = str(APP_ROOT / "app.py")
    db_path = APP_ROOT / "database.db"
    
    sep = ':' if os.name == 'posix' else ';'
    add_data = [
        f'{APP_ROOT / "templates"}{sep}templates',
        f'{APP_ROOT / "static"}{sep}static',
        f'{APP_ROOT / "masters"}{sep}masters',
        f'{db_path}{sep}.',
    ]

    # --- 引数設定（specpathを追加してルートを汚さないようにする） ---
    args = [
        SCRIPT,
        f'--name={APP_NAME}',
        '--noconfirm',
        '--windowed',
        '--clean',
        '--target-arch=arm64',
        f'--distpath={DIST_DIR}',
        f'--workpath={WORK_DIR}',
        f'--specpath={WORK_DIR}', # specファイルをbuildフォルダ内に作成
        '--osx-bundle-identifier=com.rfunyo.system',
    ]
    
    for data in add_data: args.append(f'--add-data={data}')
    hidden_imports = ['openpyxl', 'pandas', 'sqlite3', 'webview', 'objc', 'Foundation', 'AppKit', 'WebKit']
    for imp in hidden_imports: args.append(f'--hidden-import={imp}')

    try:
        PyInstaller.__main__.run(args)
        fix_plist_and_register()
        print(f"\n✅ ビルド完了！\n{DIST_DIR}/{APP_NAME}.app")
    except Exception as e:
        print(f"\n❌ ビルドエラー: {e}")

if __name__ == "__main__":
    build()
