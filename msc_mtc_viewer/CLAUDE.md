# CLAUDE.md — MSC_MTC_Viewer

## プロジェクト概要

USB-MIDI I/F や IAC から受信した MIDI Show Control (MSC) / MTC メッセージをリアルタイムで解析・表示する現場モニターツール。
Flask + pywebview + PyInstaller による macOS .app。

- **参考アプリ**: `midi_monitor_decorder`（.mmon ファイルの解析ツール）と同じアーキテクチャパターン
- **MSC 仕様**: `../midi_monitor_decorder/docs/MIDI1.0_MSC.md` を参照

## アーキテクチャ

- `decoder.py` — MSC バイト列デコードの純粋関数モジュール。rtmidi 依存なし。
- `midi_receiver.py` — python-rtmidi によるライブ MIDI ポート管理 + スレッドセーフ Queue。
- `persistence.py` — 接続履歴・UI 設定を `settings.json` に保存・ロード。read-then-merge パターン。
- `app.py` — Flask サーバー（スレッド）+ pywebview ネイティブウィンドウ。HTML/JS UI 埋め込み。
- `build_app.py` — PyInstaller で `dist/MSC_MTC_Viewer_{arch}.app` を生成（`--arch arm64|x86_64|x86_64_1013_py312`）。
- `config.json` — バージョン・ウィンドウサイズ等の設定を一元管理。`app.py` と `build_app.py` の両方から参照する。PyInstaller バンドルにも同梱される。
- `build/` — 社内配布用パッケージ（Apple Silicon / Intel / Intel 10.13.6）と受け手向け README。

## 開発コマンド

```bash
# 初回セットアップ
bash setup.sh            # arm64 (.venv) のみ
bash setup.sh --x86      # x86_64 (.venv_x86) のみ（Rosetta 2 経由）
bash setup.sh --x86-1013-py312  # macOS 10.13.6 向け Intel (.venv_x86_1013_py312)
bash setup.sh --all      # arm64 と x86_64

# 起動
.venv/bin/python app.py

# lint / format
.venv/bin/ruff check decoder.py midi_receiver.py persistence.py app.py
.venv/bin/ruff format decoder.py midi_receiver.py persistence.py app.py

# .app ビルド（Ruff チェックを含む）
.venv/bin/python build_app.py                  # arm64 と x86_64 を両方ビルド
.venv/bin/python build_app.py --arch arm64     # Apple Silicon 専用
.venv/bin/python build_app.py --arch x86_64   # Intel 専用（.venv_x86 が必要）
.venv/bin/python build_app.py --arch x86_64_1013_py312  # Intel macOS 10.13.6 専用
```

## 現行の配布系統

- Apple Silicon: `dist/MSC_MTC_Viewer_arm64.app` → `build/apple_silicon_package/`
- Intel Mac: `dist/MSC_MTC_Viewer_x86_64.app` → `build/intel_mac_package/`
- Intel Mac 10.13.6: `dist/MSC_MTC_Viewer_x86_64_1013_py312.app` → `build/intel_mac_1013_package/`

インストーラは Automator で作成した `Install_*.app` を使う。Terminal スクリプト運用は廃止。
10.13.6 対応は Python 3.12 + `python-rtmidi` の公式 x86_64 wheel 前提。

## コーディングルール

- Ruff を使用（`pyproject.toml` 参照）。ビルド前に必ず通すこと。
- line-length: 100

## スレッドモデル

```
rtmidi コールバックスレッド       Flask SSE スレッド              pywebview メインスレッド
───────────────────────────       ─────────────────               ────────────────────────
MidiIn callback (port A/B)        get_next_message(timeout=0.5)   webview.start()
  raw bytes                         QF: _handle_qf_message()            │
      │                             SysEx: Full Frame / MSC       http://127.0.0.1:<動的PORT>
      ▼                             _log_buffer に追記                   │
  _message_queue.put_nowait()       SSE yield                     ブラウザ (WebKit)
  (queue.Queue: スレッドセーフ)          │                         EventSource
                                        ▼                           appendRow() ← SSE "msc"/"mtc"
                                   keepalive (500ms 無通信時)       renderRows() ← MAX_ROWS 切替時

ポート監視スレッド（port-monitor）
─────────────────────────────────
3 秒ごとに available / connected / saved_ports を比較
  ├─ connected にあるが available にない → disconnect_port() でクリーンアップ
  └─ saved_ports にあり available かつ未接続 → connect_port() で再接続
```

- `queue.Queue` は rtmidi の C スレッドから安全に `put_nowait()` できる
- `_log_buffer` は `collections.deque(maxlen=MAX_LOG_ROWS)` — 上限超過時に古い要素を自動削除
- `_log_buffer` / `_qf_nibbles` の読み書きはそれぞれ `_log_lock` / `_mtc_lock` で保護
- `drain_queue()` は `api_clear()` のみで使用（SSE ループでは使わない）
- Flask ポートは `make_server('127.0.0.1', 0, app, threaded=True)` で動的割り当て（`threaded=True` 必須: SSE が単一スレッドを占有するため）
- ポート確定待ちは `threading.Event`（`_port_ready.wait(timeout=10.0)`）で実装

## python-rtmidi の ignore_types 設定

`connect_port()` 内で以下のように設定している:

```python
midi_in.ignore_types(sysex=False, timing=False, active_sense=True)
```

| 引数 | 値 | 意味 |
|------|----|------|
| `sysex` | `False` | SysEx (0xF0) を**受信**する |
| `timing` | `False` | MTC Quarter Frame (0xF1) を**受信**する |
| `active_sense` | `True` | Active Sensing (0xFE) を**無視**する |

**重要:** RtMidi の CoreMIDI バックエンドでは `timing` フラグが MIDI Clock (0xF8) だけでなく
**MTC Quarter Frame (0xF1) も制御**する。`timing=True` にすると MTC QF が受信できなくなるため、
`timing=False` は MIDI Clock を受け取るためではなく **MTC QF を受信するために必須**の設定。

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

SSE（`/api/events`）の `json.dumps` は `ensure_ascii=False` を使用する。
JSON API レスポンス（`_CT_JSON` 系）は `ensure_ascii=True`（デフォルト）で `\uXXXX` エスケープを維持する。

### `<script>` 内の日本語文字列は `String.fromCharCode()` を使う

`xmlcharrefreplace` は `<script>` タグ内の文字列リテラルも変換する。
HTML エンティティ（`&#XXXX;`）は HTML パーサーが解釈するものであり、JS エンジンは解釈しないため文字化けする。

**NG パターン（文字化けする）:**
```python
# Python 文字列中の日本語 → xmlcharrefreplace → &#XXXX; → JS が解釈できない
'日曜日'          # → &#26085;&#26332;&#26085; （JSでは文字化け）
'\u65e5\u66dc\u65e5'  # Python では同じ文字なので同様に変換される
```

**OK パターン（正しく動作する）:**
```javascript
// String.fromCharCode() は純粋な ASCII → 変換されない
const _fc = String.fromCharCode;
const WEEKDAYS = [
  _fc(0x65e5,0x66dc,0x65e5),  // 日曜日
  _fc(0x6708,0x66dc,0x65e5),  // 月曜日
  // ...
];
const date = now.getFullYear() + _fc(0x5e74) + ...;  // 年
```

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

## MTC Quarter Frame 処理（app.py）

MTC QF（`0xF1`）は 8 種類の nibble（type 0〜7）を順番に受信し、8 個揃ったら 1 フレームのタイムコードを復元する。

### 状態変数・定数

| 名前 | 型 | 説明 |
|------|----|------|
| `QF_TIMEOUT_SEC` | `float` | QF が途切れてリセットするまでの閾値（0.25 秒） |
| `_qf_nibbles` | `list[int \| None]` | 8 スロットの nibble バッファ |
| `_qf_last_type` | `int \| None` | 直前に受信した nibble_type（0〜7） |
| `_qf_last_time` | `float \| None` | 直前の QF 受信時刻（`time.monotonic()`） |
| `_mtc_lock` | `threading.Lock` | 上記全変数の保護ロック |

### ヘルパー関数

**`_reset_qf_state()`** — `_qf_nibbles` / `_qf_last_type` / `_qf_last_time` を一括リセット。
**必ず `_mtc_lock` 保持中に呼ぶこと**。外部から単独で呼ばない。

**`_handle_qf_message(raw_qf)`** — QF 1 メッセージを処理し、8 nibble 揃ったら MTC イベント dict を返す。
内部で `_mtc_lock` を取得し、以下の順で処理する:
1. タイムアウトチェック: `_qf_last_time` から `QF_TIMEOUT_SEC` 超過 → リセット
2. 順序検証: `(_qf_last_type + 1) % 8` でなく、かつ同 type でもない → リセット（再同期）
3. nibble 書き込み・状態更新
4. 8 nibble 揃ったら復元 → 全リセットしてイベント dict 返却

### QF リセットのトリガー

| タイミング | 処理 |
|-----------|------|
| QF タイムアウト（0.25s 以上空白） | `_handle_qf_message()` 内でリセット |
| QF 順序違反 | `_handle_qf_message()` 内でリセット・再同期 |
| 8 nibble 揃って復元後 | `_handle_qf_message()` 内でリセット |
| MTC Full Frame SysEx 受信 | `generate()` 内で `with _mtc_lock: _reset_qf_state()` |
| `/api/clear` 実行 | `api_clear()` 内で `with _mtc_lock: _reset_qf_state()` |

### MTC イベントのフォーマット（SSE）

```json
{"event_type": "mtc", "hours": 1, "minutes": 30, "seconds": 0, "frames": 12, "fps_code": 1}
```

`fps_code`: 0=24fps, 1=25fps, 2=29.97fps(DF), 3=30fps

---

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
| GET | `/api/events` | SSE（リアルタイム配信、500ms keepalive）|
| POST | `/api/clear` | ログバッファ・QF 状態クリア（Queue も空にする） |
| POST | `/api/export` | CSV ダウンロード（`msc_log_YYYYMMDD_HHMMSS.csv`） |
| GET | `/api/logs?limit=N` | ログバッファ末尾 N 件を返す（`renderRows()` が使用） |
| GET | `/api/settings` | UI 設定取得（`raw_hex_visible` 等） |
| POST | `/api/settings/raw_hex_visible` | Raw Hex 列表示状態を保存 `{"visible": bool}` |

## JS テーブル描画関数の使い分け

| 関数 | 用途 | DOM 操作方針 |
|------|------|-------------|
| `appendRow(row)` | SSE リアルタイム追加（1件） | 直接 `tbody.appendChild`、毎回 `updateCount()` / autoscroll / search-match 判定 |
| `renderRows(rows)` | 一括再描画（MAX_ROWS 切替時など） | `DocumentFragment` で全行生成後に1回 `appendChild`、`updateCount()` / `runSearch()` / autoscroll を最後に1回のみ |

- `renderRows()` は `changeMaxRows()` から呼ぶ。`appendRow()` は呼ばない。
- `renderRows()` 内では MAX_ROWS による行削除を行わない（サーバーが `limit` 件を返すため不要）。

---

## settings.json 永続化（persistence.py）

保存先: `config.json` の `settings_dir`（デフォルト: `~/Library/Application Support/MSC_MTC_Viewer/settings.json`）

**read-then-merge パターン**: 保存時は既存 JSON を読み込んでからキーを上書きして書き直す。
個別キーの保存が他のキーを破壊しない。

```python
persistence.init(settings_dir)              # app.py 起動時に設定ディレクトリを初期化
persistence.load_saved_ports()              # 保存済みポート名リスト → list[str]
persistence.save_connected_ports(ports)     # 接続中ポートを保存
persistence.load_raw_hex_visible()          # Raw Hex 表示状態 → bool（デフォルト True）
persistence.save_raw_hex_visible(bool)      # Raw Hex 表示状態を保存
persistence.load_max_display_rows()         # 最大表示件数 → int（デフォルト 500）
persistence.save_max_display_rows(rows)     # 最大表示件数を保存
```

## config.json の構造

```json
{
  "version": "1.0.0",
  "app_name": "MSC_MTC_Viewer",
  "developer": "Satoshi Tateishi",
  "updated": "2026-03-24",
  "bundle_id": "com.midi.mscmonitor",
  "port": 0,                   // 0 = 動的割り当て
  "window_width": 1200,
  "window_height": null,       // null = 画面高さに合わせる
  "window_maximize": true,     // 起動時にウィンドウを最大化
  "window_min_width": 1150,    // 最小幅（下記根拠を参照）
  "window_min_height": 400,
  "window_x": null,            // null = OS デフォルト位置
  "window_y": null,
  "max_log_rows": 5000,        // ログバッファ最大行数（サーバー側保持上限）
  "export_dir": "~/Downloads/MSC_MTC_Viewer_CSV",
  "settings_dir": "~/Library/Application Support/MSC_MTC_Viewer"
}
```

## UI レイアウト構造

body は `flex-direction: column` の縦並び。main-content が `flex-direction: row` の左右分割。

```
┌──────────────────────────────────────────────────────┐
│ header (flex-shrink: 0)                              │
│   ポートドロップダウン（折りたたみ・複数選択）・再スキャン  │
├──────────────────────────┬───────────────────────────┤
│ left-panel (flex:1)      │ right-panel (380px固定)    │
│  ├ toolbar               │  ├ last-msc (flex:1)       │
│  │   クリア / CSV /       │  │   最終受信 MSC 大型表示  │
│  │   Raw Hex / 自動スクロール  last-msc の上が MSC     │
│  └ table-wrap (flex:1)   │  └ mtc-viewer (flex:1)     │
│      MSC ログテーブル     │      MTC タイムコード       │
│      （列幅固定+filler）  │      mtc-viewer は下半分   │
├──────────────────────────┴───────────────────────────┤
│ clock-bar (flex-shrink: 0) — システム時計（HH:MM ss 日付）│
└──────────────────────────────────────────────────────┘
```

**Raw Hex 非表示時のレイアウト変化:**
- `body.raw-hex-hidden` クラスで CSS を切り替え
- `left-panel`: `flex: 0 0 730px`（固定幅・列合計 710px + スクロールバー）
- `right-panel`: `flex: 1; min-width: 420px`（残余幅いっぱいに拡大）
- MTC フォント: 48px → 64px、MSC Q_number フォント: 68px → 96px

**MSC ログテーブルの列構成:**

| 列 | 幅 | 備考 |
|----|-----|------|
| 時刻 | 100px | |
| ポート | 160px | |
| Dev ID | 70px | |
| Format | 130px | |
| Command | 110px | |
| Q_number | 80px | |
| Q_list | 60px | |
| Raw Hex | 220px | Raw Hex 非表示時 width:0 |
| (filler) | 残余 | テーブルを left-panel 全幅に埋める |

`table { width: 100%; table-layout: fixed }` + filler 列で空白なしを実現。

**最小ウィンドウ幅 1150px の根拠:**
- Raw Hex 表示時: 左パネル最小(600) + 右パネル固定(380) = 980px
- Raw Hex 非表示時: 左パネル固定(730) + 右パネル最小(420) = 1150px
  ※ 64px bold の HH:MM:SS.FF ≒ 402px 必要なため 420px を確保
→ 両状態をカバーする 1150px を採用

## ウィンドウ起動設定

```python
window = webview.create_window(
    title=APP_NAME,
    url=f"http://127.0.0.1:{_PORT}/",
    width=WINDOW_WIDTH,
    resizable=True,
    min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
)
webview.start(lambda: window.maximize() if WINDOW_MAXIMIZE else None)
```

- `min_size` は `create_window()` のパラメータ。`config.json` の `window_min_width` / `window_min_height` で管理。
- `webview.start(func)` に渡した関数は GUI 起動後に別スレッドで実行される。
- `WINDOW_MAXIMIZE=true`（config.json）のとき起動直後に最大化。

## macOS 解像度と CSS px

pywebview（WKWebView）は **CSS px = macOS points（論理ピクセル）** を使用する。
Retina ディスプレイの物理解像度（例: 2560×1664）は CSS px とは異なる。

| デバイス | 物理解像度 | CSS px 幅（デフォルト） |
|---------|----------|----------------------|
| MacBook Air 13" M1/M2 | 2560×1600/1664 | **1280px** |
| MacBook Air 13" M2（より多くのスペース） | 2560×1664 | **1470px** |
| MacBook Pro 14" M3 | 3024×1964 | **1512px** |
| MacBook Pro 16" M3 | 3456×2234 | **1728px** |
| iMac 24" M3 | 4480×2520 | **2240px** |
| iMac 27" / Studio Display | 5120×2880 | **2560px** |

**レイアウト評価（最大化時）:**
- MBA/MBP 13"〜16"（1280〜1728px）: 両 Raw Hex 状態で問題なし ✅
- iMac/Studio Display（2240px〜）: Raw Hex 表示時に右パネル(380px)が画面の 15〜17% にとどまり
  相対的に小さく見えるが、機能上の問題はない

## システム時計（clock-bar）

UI 最下部に `HH:MM ss` と日付・曜日を常時表示。

**秒境界への同期:**
`setInterval(fn, 1000)` は開始タイミング次第で最大 1 秒の遅延が生じる。
`setTimeout` で次の秒境界まで待機してから `setInterval` を開始することで解消。

```javascript
updateClock();
setTimeout(() => {
  updateClock();
  setInterval(updateClock, 1000);
}, 1000 - new Date().getMilliseconds());
```

## PyInstaller ビルド時の注意

- `--add-data` で `decoder.py`, `midi_receiver.py`, `persistence.py`, `config.json` を同梱すること
- hidden imports: `flask`, `werkzeug`, `webview`, `objc`, `Foundation`, `AppKit`, `WebKit`, `rtmidi`
- ビルドには python.org 版 Python 3.13 が必要（`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`）

### アーキテクチャ別ビルド

`python-rtmidi 1.5.8` は `meson-python` ベースのため `ARCHFLAGS` による universal2 ビルドが**不可能**。
Intel / Apple Silicon それぞれ専用の .app を別ファイルとして生成する。

| arch | venv | PyInstaller オプション | 出力 |
|---|---|---|---|
| arm64 | `.venv` | `--target-arch=arm64` | `MSC_MTC_Viewer_arm64.app` |
| x86_64 | `.venv_x86` | `--target-arch=x86_64` | `MSC_MTC_Viewer_x86_64.app` |

- **arm64 venv**: `setup.sh` が python.org 版 Python 3.13 (universal2) で作成。`markupsafe` は arm64 専用 wheel のため `ARCHFLAGS="-arch x86_64 -arch arm64"` でソースビルド（`setup.sh` で自動対応済み）。
- **x86_64 venv**: `setup.sh --x86` が `arch -x86_64 python3 -m venv .venv_x86` で作成（Rosetta 2 経由）。`python-rtmidi` は pip が x86_64 wheel を自動選択するため ARCHFLAGS 不要。
- x86_64 ビルド時は `build_app.py` が `arch -x86_64 .venv_x86/bin/pyinstaller` をサブプロセスで呼ぶ。
