# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/satoshi/python_works/rf_unyo/ch_list/app.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/satoshi/python_works/rf_unyo/ch_list/templates', 'templates'), ('/Users/satoshi/python_works/rf_unyo/ch_list/static', 'static'), ('/Users/satoshi/python_works/rf_unyo/ch_list/masters', 'masters'), ('/Users/satoshi/python_works/rf_unyo/ch_list/database.db', '.')],
    hiddenimports=['openpyxl', 'pandas', 'sqlite3', 'webview', 'objc', 'Foundation', 'AppKit', 'WebKit'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RF_Unyo_System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RF_Unyo_System',
)
app = BUNDLE(
    coll,
    name='RF_Unyo_System.app',
    icon=None,
    bundle_identifier='com.rfunyo.system',
)
