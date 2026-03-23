# MSC Decoder

MIDI Monitor (.mmon) で保存されたログファイルから MSC（MIDI Show Control）イベントを抽出し、表形式で確認できる現場ツール。

## 主な機能

- `.mmon` ファイルをドラッグ＆ドロップするだけで MSC イベントを一覧表示
- 絶対時刻（`HH時MM分SS秒`）で表示
- 専用ネイティブウィンドウ（pywebview）で表示
- CLI でも動作（CSV 出力）

## 出力カラム

| タイムスタンプ | MSC | コマンド | page | Cue No. |
|---|---|---|---|---|
| 21時52分11秒 | MSC | GO | 1 | 0.7 |

## セットアップ

**前提**: universal2（Intel + Apple Silicon 両対応）ビルドを行う場合は、[python.org](https://www.python.org/downloads/macos/) から Python 3.13 の macOS universal2 インストーラを事前にインストールしてください。

```bash
# 初回のみ（.venv 作成 + 依存パッケージのインストール）
bash setup.sh
```

python.org 版 Python 3.13 が検出された場合は自動的に universal2 環境を構築します。未インストールの場合は arm64（Apple Silicon 専用）でセットアップします。

## 起動（開発モード）

```bash
.venv/bin/python app.py
```

## CLI 使用方法

```bash
.venv/bin/python decoder.py input.mmon output.csv
```

## .app ビルド

```bash
.venv/bin/python build_app.py
# → dist/MSC Decoder.app が生成される（universal2）
```

生成された `dist/MSC Decoder.app` は Intel Mac・Apple Silicon Mac のどちらでもネイティブ動作します。

## 設定（config.json）

アプリの動作設定を `config.json` で管理しています。

| キー | 内容 | デフォルト |
|---|---|---|
| `version` | アプリバージョン | `"1.0.0"` |
| `app_name` | アプリ名 | `"MSC Decoder"` |
| `bundle_id` | macOS バンドル ID | `"com.msc.decoder"` |
| `port` | Flask サーバーポート | `8765` |
| `window_width` | ウィンドウ幅（px） | `520` |
| `window_height` | ウィンドウ高さ（px）。`null` で画面高さに自動設定 | `null` |
| `max_upload_mb` | アップロード上限（MB） | `50` |

## ファイル構成

```
midi_monitor_decorder/
├── app.py            # Flask + pywebview ネイティブウィンドウアプリ
├── decoder.py        # MSC デコードロジック / CLI
├── build_app.py      # .app ビルドスクリプト（PyInstaller）
├── config.json       # アプリ設定
├── setup.sh          # 初回 venv セットアップ
├── requirements.txt  # 依存パッケージ（バージョン固定）
├── pyproject.toml    # Ruff 設定
└── sample_file/      # サンプル .mmon ファイル
```

## 対応 MSC コマンド

| コマンド | 内容 |
|---|---|
| GO | キュー実行（cue / page を表示） |
| STOP | 停止 |
| RESUME | 再開 |
| SET | セット |
| FIRE | ファイア |
