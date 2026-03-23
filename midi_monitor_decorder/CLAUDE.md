# CLAUDE.md — MSC Decoder

## プロジェクト概要

MIDI Monitor (.mmon) から MSC イベントを抽出・表示する現場ツール。
Flask + pywebview + PyInstaller による macOS .app。

## アーキテクチャ

- `decoder.py` — .mmon パース・MSCデコードのコアロジック。CLI としても動作。
- `app.py` — Flask サーバー（スレッド）+ pywebview ネイティブウィンドウ。
- `build_app.py` — PyInstaller で `dist/MSC Decoder.app` を生成。
- `config.json` — バージョン・ポート・ウィンドウサイズ等の設定を一元管理。`app.py` と `build_app.py` の両方から参照する。PyInstaller バンドルにも同梱される。

## 開発コマンド

```bash
# 初回のみ
bash setup.sh

# 起動
.venv/bin/python app.py

# CLI
.venv/bin/python decoder.py sample_file/log_msc.mmon output.csv

# lint / format
.venv/bin/ruff check decoder.py app.py build_app.py
.venv/bin/ruff format decoder.py app.py build_app.py

# .app ビルド（Ruff チェックを含む）
.venv/bin/python build_app.py
```

## コーディングルール

- Ruff を使用（`pyproject.toml` 参照）。ビルド前に必ず通すこと。
- line-length: 100

## デコードロジック（decoder.py）

- `.mmon` は Apple Binary plist（外側）+ NSKeyedArchive（内側）の二重構造
- `messageData` キーに内側 plist がバイナリで格納される
- 各メッセージの `clockTimeStamp` は Mac 参照時刻（2001-01-01 UTC 基準）
  - Unix 変換: `unix_ts = clockTimeStamp + 978307200`
- SysEx データ（`data` フィールド）は F0/F7 を除いたボディのみ格納
- MSC 判定: `statusByte == 0xF0` かつ `data[0]==0x7F` かつ `data[2]==0x02`

## MSC 1.1 GO コマンドのデータ構造

```
F0 7F <device_ID> 02 <command_format> 01 <Q_number> 00 <Q_list> 00 <Q_path> F7
```

| MSC 1.1 正式名 | row dict キー | 説明 |
|---|---|---|
| Q_number | `"cue"` | キュー番号（オプション、省略時は次のキューをGO） |
| Q_list | `"page"` | キューリスト番号（照明ではエグゼキュータ/ページに相当） |
| Q_path | *(無視)* | キューパス（ファイルパス相当、表示不要） |

- Q_number を省略したベアGO（`F0 7F .. 02 .. 01 F7`）は MSC 1.1 の有効コマンド
  → `cue=""`, `page=""` として記録される
- フィールドは `0x00` で区切られ、位置が意味を持つ（空フィールドも位置を保持）

## row dict の構造

```python
{
    "timestamp": "21時52分11秒",       # 表示用（ローカル時刻）
    "date": "2026-03-23",              # 内部保持（日付またぎ対応）
    "datetime_iso": "2026-03-23T21:52:11",
    "msc": "MSC",
    "command": "GO",
    "page": "1",                       # GO のみ、Q_list に対応。なければ ""
    "cue": "0.7",                      # GO のみ、Q_number に対応。なければ ""
    "raw_hex": "F0 7F 01 02 7F 01 ...",
}
```

## PyInstaller ビルド時の注意

- `decoder.py` と `config.json` を `--add-data` で同梱すること
- hidden imports: `flask`, `werkzeug`, `webview`, `objc`, `Foundation`, `AppKit`, `WebKit`
- universal2（Intel + Apple Silicon 両対応）ビルドには python.org 版 Python 3.13 が必要
  - `setup.sh` が自動検出して universal2 環境を構築する
  - `markupsafe` は arm64 専用 wheel が配布されているため、ソースから `ARCHFLAGS="-arch x86_64 -arch arm64"` 付きでビルドすること（`setup.sh` で自動対応済み）
