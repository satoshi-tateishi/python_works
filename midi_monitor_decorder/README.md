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

```bash
# 初回のみ（.venv 作成 + 依存パッケージのインストール）
bash setup.sh
```

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
# → dist/MSC Decoder.app が生成される
```

## ファイル構成

```
midi_monitor_decorder/
├── app.py            # Flask + pywebview ネイティブウィンドウアプリ
├── decoder.py        # MSC デコードロジック / CLI
├── build_app.py      # .app ビルドスクリプト（PyInstaller）
├── setup.sh          # 初回 venv セットアップ
├── requirements.txt  # 依存パッケージ
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
