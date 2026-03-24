# CLAUDE.md — MIDI MSC Monitor

## プロジェクト概要

USB-MIDI I/F や IAC から受信した MIDI Show Control (MSC) メッセージをリアルタイムで解析・表示する現場モニターツール。
Flask + pywebview + PyInstaller による macOS .app。

- **参考アプリ**: `midi_monitor_decorder`（.mmon ファイルの解析ツール）と同じアーキテクチャパターン
- **MSC 仕様**: `../midi_monitor_decorder/docs/MIDI1.0_MSC.md` を参照

## アーキテクチャ

- `decoder.py` — MSC バイト列デコードの純粋関数モジュール。rtmidi 依存なし。
- `midi_receiver.py` — python-rtmidi によるライブ MIDI ポート管理 + スレッドセーフ Queue。
- `app.py` — Flask サーバー（スレッド）+ pywebview ネイティブウィンドウ。HTML/JS UI 埋め込み。
- `build_app.py` — PyInstaller で `dist/MIDI MSC Monitor.app` を生成。
- `config.json` — バージョン・ウィンドウサイズ等の設定を一元管理。`app.py` と `build_app.py` の両方から参照する。PyInstaller バンドルにも同梱される。

## 開発コマンド

```bash
# 初回のみ
bash setup.sh

# 起動
.venv/bin/python app.py

# lint / format
.venv/bin/ruff check decoder.py midi_receiver.py app.py
.venv/bin/ruff format decoder.py midi_receiver.py app.py

# .app ビルド（Ruff チェックを含む）
.venv/bin/python build_app.py
```

## コーディングルール

- Ruff を使用（`pyproject.toml` 参照）。ビルド前に必ず通すこと。
- line-length: 100

## スレッドモデル

```
rtmidi コールバックスレッド       Flask SSE スレッド          pywebview メインスレッド
───────────────────────────       ─────────────────           ────────────────────────
MidiIn callback (port A/B)        drain_queue() ループ        webview.start()
  raw bytes                         decode_msc_bytes()              │
      │                             _log_buffer に追記        http://127.0.0.1:<動的PORT>
      ▼                             SSE yield                       │
  _message_queue.put_nowait()            │                   ブラウザ (WebKit)
  (queue.Queue: スレッドセーフ)          ▼                   EventSource → appendRow()
```

- `queue.Queue` は rtmidi の C スレッドから安全に `put_nowait()` できる
- `_log_buffer` の読み書きは `threading.Lock` で保護
- Flask ポートは `make_server('127.0.0.1', 0, app, threaded=True)` で動的割り当て（`threaded=True` 必須: SSE が単一スレッドを占有するため）

## python-rtmidi ポート名の文字化け対策

macOS の CoreMIDI が返す UTF-8 文字列を python-rtmidi が **Mac Roman** として誤デコードするため、日本語ポート名が文字化けする。

**現象**: `ド`(UTF-8: `E3 83 89`) → Mac Roman 誤読 → `„Éâ`

**修正** (`midi_receiver.py` の `_fix_port_name`):
```python
name.encode("mac_roman").decode("utf-8")
```
Mac Roman として再エンコードすることで元の UTF-8 バイト列を復元し、正しくデコードする。
ASCII ポート名は変換前後で同一なので影響なし。

## HTML の文字化け対策

pywebview の WKWebView が Content-Type の charset を無視するケースがあるため、HTML は非ASCII文字を `&#XXXX;` 形式の XML 数値文字参照に変換して配信する。

```python
_HTML_UI_BYTES = HTML_UI.encode("ascii", "xmlcharrefreplace")
```

JSON レスポンスも `ensure_ascii=True`（デフォルト）で `\uXXXX` エスケープを使用し、文字コード問題を完全に回避する。

## MSC デコードロジック（decoder.py）

MSC フォーマット:
```
F0 7F <device_ID> 02 <command_format> <command> [data] F7
```

| バイト位置 | 内容 |
|-----------|------|
| raw[0] | `0xF0` — SysEx 開始 |
| raw[1] | `0x7F` — Universal Real-Time SysEx |
| raw[2] | device_ID |
| raw[3] | `0x02` — MSC Sub-ID #1 |
| raw[4] | command_format |
| raw[5] | command |
| raw[6..n-1] | data（省略可） |
| raw[-1] | `0xF7` — SysEx 終了 |

**device_ID の表示変換:**
- `0x00`–`0x6F` → 数値（個別デバイス）
- `0x70`–`0x7E` → `GRP_n`（グループ）
- `0x7F` → `ALL`（全デバイス）

**不明なバイト:** `FMT_0xNN` / `CMD_0xNN` で表示（サイレント破棄しない）

**Q_number / Q_list のパース:**
- `0x00` 区切りの ASCII フィールド（数字 `0x30`–`0x39` と小数点 `0x2E`）
- Q_number を持つコマンド: GO(01), STOP(02), RESUME(03), TIMED_GO(04), LOAD(05), GO_OFF(0B)
- ベア GO（Q_number 省略）は有効: `q_number=""`, `q_list=""`

## row dict の構造（`decode_msc_bytes()` の戻り値）

```python
{
    "timestamp": "21:52:11.123",   # app.py で付与（ローカル時刻、ミリ秒付き）
    "port": "IAC Driver Bus 1",    # app.py で付与（受信ポート名）
    "device_id": "ALL",            # "ALL" / "GRP_n" / 数値文字列
    "cmd_format": "Lighting",      # command_format の表示名
    "command": "GO",               # command の表示名
    "q_number": "1.5",             # Q_number。なければ ""
    "q_list": "2",                 # Q_list。なければ ""
    "raw_hex": "F0 7F 7F 02 01 01 31 2E 35 00 32 F7",
}
```

## midi_receiver.py の主要 API

```python
get_available_ports() -> list[str]   # 利用可能な MIDI 入力ポート一覧
get_connected_ports() -> list[str]   # 現在接続中のポート一覧
connect_port(port_name: str) -> bool # ポートを開いてコールバックをセット
disconnect_port(port_name: str)      # ポートを閉じる
disconnect_all()                     # すべてのポートを閉じる
drain_queue() -> list[dict]          # Queue を非ブロッキングで全取り出し
```

- `connect_port` は毎回 `get_ports()` を呼んでインデックスを取得する（USB 抜き差し後の再接続に対応）
- コールバック内では SysEx（`raw[0] == 0xF0`）のみ Queue に投入

## Flask API エンドポイント

| Method | Path | 説明 |
|--------|------|------|
| GET | `/` | HTML UI |
| GET | `/api/ports` | 利用可能ポート一覧（接続状態付き） |
| POST | `/api/ports/connect` | ポート接続 `{"port": "..."}` |
| POST | `/api/ports/disconnect` | ポート切断 `{"port": "..."}` |
| GET | `/api/events` | SSE（リアルタイム MSC 配信、20ms ポーリング） |
| POST | `/api/clear` | ログバッファクリア（Queue も空にする） |
| GET | `/api/export` | CSV ダウンロード（`msc_log_YYYYMMDD_HHMMSS.csv`） |

## config.json の構造

```json
{
  "version": "1.0.0",
  "app_name": "MIDI MSC Monitor",
  "bundle_id": "com.midi.mscmonitor",
  "port": 0,           // 0 = 動的割り当て
  "window_width": 1100,
  "window_height": null,  // null = 画面高さに合わせる
  "window_x": null,       // null = OS デフォルト位置
  "window_y": null
}
```

## PyInstaller ビルド時の注意

- `--add-data` で `decoder.py`, `midi_receiver.py`, `config.json` を同梱すること
- hidden imports: `flask`, `werkzeug`, `webview`, `objc`, `Foundation`, `AppKit`, `WebKit`, `rtmidi`
- universal2（Intel + Apple Silicon 両対応）ビルドには python.org 版 Python 3.13 が必要
  - `setup.sh` が `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` を自動検出
  - `markupsafe` は arm64 専用 wheel が配布されているため、`ARCHFLAGS="-arch x86_64 -arch arm64"` でソースビルド（`setup.sh` で自動対応済み）
  - `python-rtmidi` は macOS 向け fat wheel が PyPI にあるため通常の `pip install` で対応
