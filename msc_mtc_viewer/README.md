# MSC_MTC_Viewer

USB-MIDI インターフェースや IAC から受信した **MIDI Show Control (MSC)** および **MTC タイムコード**をリアルタイムで解析・表示する macOS デスクトップアプリ。

## 対応環境

- macOS（Intel / Apple Silicon）
- Python 3.13
- macOS 10.13.6 向け Intel ビルドのみ Python 3.12 を併用

---

## 機能

### MIDI ポート管理
- 接続中の USB-MIDI インターフェースおよび IAC をチェックボックスで複数選択可能
- 「再スキャン」ボタンでポート一覧を更新
- 前回使用したポートを起動時に自動接続（`~/Library/Application Support/MSC_MTC_Viewer/settings.json` に保存）

### MSC デコード
受信した SysEx メッセージを解析し、以下の情報を表示する。

| 列 | 内容 |
|----|------|
| 時刻 | 受信時刻（ミリ秒精度） |
| ポート | 受信した MIDI ポート名 |
| Dev ID | デバイス ID（数値 / `GRP_n` / `ALL`） |
| Format | コマンドフォーマット（`Lighting`, `Sound` など） |
| Command | コマンド名（`GO`, `STOP`, `RESUME` など） |
| Q_number | キュー番号 |
| Q_list | キューリスト番号 |
| Raw Hex | 生バイト列（16進数・表示切替可） |

#### 対応コマンドフォーマット
`Lighting`, `Moving Lights`, `Colour Changers`, `Strobes`, `Lasers`, `Chasers`,
`Sound`, `Music`, `CD Players`, `EPROM Playback`, `Audio Tape Machines`, `Intercoms`, `Amplifiers`, `Audio Effects Devices`, `Equalizers`,
`Machinery` 系, `Video` 系, `Projection` 系, `Process Control` 系, `Pyro` 系, `All Types`

#### 対応コマンド
`GO`, `STOP`, `RESUME`, `TIMED_GO`, `LOAD`, `SET`, `FIRE`, `ALL_OFF`, `RESTORE`, `RESET`, `GO_OFF`,
`GO_JAM_CLOCK`, `STANDBY+/-`, `SEQUENCE+/-`, `START_CLOCK`, `STOP_CLOCK`, `ZERO_CLOCK`, `SET_CLOCK`,
`MTC_CHASE_ON`, `MTC_CHASE_OFF`, `OPEN_CUE_LIST`, `CLOSE_CUE_LIST`, `OPEN_CUE_PATH`, `CLOSE_CUE_PATH`,
`STANDBY_2PC`, `STANDING_BY`, `GO_2PC`, `COMPLETE`, `CANCEL`, `CANCELLED`, `ABORT`

未知のコマンドバイトは `CMD_0xNN` / `FMT_0xNN` 形式で表示（サイレント破棄しない）。

### MTC タイムコード表示
- MTC Quarter Frame（`0xF1`）および Full Frame SysEx を受信してタイムコードを復元・表示
- `HH:MM:SS.FF` 形式、FPS（24 / 25 / 29.97DF / 30）を表示
- 受信順序検証・タイムアウトリセット（0.25s）により、接続直後や途切れ後でも正確に同期

### ログ操作
- **クリア**: 表示中のログを消去（QF 状態もリセット）
- **CSV エクスポート**: 表示中のログを `msc_log_YYYYMMDD_HHMMSS.csv` として保存
- **Raw Hex 列**: 表示 / 非表示を切替可能
- **自動スクロール**: ON/OFF 切替
- **最大表示件数**: 100 / 200 / 500 / 1000 行から選択

---

## セットアップ

```bash
# arm64（Apple Silicon）用のみ
bash setup.sh

# x86_64（Intel）用のみ
bash setup.sh --x86

# x86_64（macOS 10.13.6 向け / Python 3.12 系）用のみ
bash setup.sh --x86-1013-py312

# arm64 と Intel の標準ビルド用
bash setup.sh --all

# 起動
.venv/bin/python app.py
```

> 標準ビルドには python.org 版 Python 3.13（universal2）が必要。
> macOS 10.13.6 向け Intel ビルドには python.org 版 Python 3.12 も必要。

---

## macOS .app ビルド

```bash
# arm64（Apple Silicon）用
.venv/bin/python build_app.py --arch arm64

# x86_64（Intel）用（事前に bash setup.sh --x86 が必要）
.venv/bin/python build_app.py --arch x86_64

# x86_64（macOS 10.13.6 向け / Python 3.12 系、事前に bash setup.sh --x86-1013-py312 が必要）
.venv/bin/python build_app.py --arch x86_64_1013_py312

# arm64 と Intel の標準ビルド
.venv/bin/python build_app.py
```

| 出力ファイル | 対象 |
|---|---|
| `dist/MSC_MTC_Viewer_arm64.app` | Apple Silicon Mac |
| `dist/MSC_MTC_Viewer_x86_64.app` | Intel Mac |
| `dist/MSC_MTC_Viewer_x86_64_1013_py312.app` | Intel Mac（macOS 10.13.6 向け / Python 3.12 系） |

> `python-rtmidi 1.5.8` は meson-python ベースのため universal2 ビルド非対応。
> アーキテクチャ別に個別ファイルを配布する。
> `x86_64_1013_py312` は Python 3.12 で `python-rtmidi` の公式 x86_64 wheel を使う前提の追加系統。

## 社内配布

- Apple Silicon 用パッケージ: `build/apple_silicon_package/`
- Intel Mac 用パッケージ: `build/intel_mac_package/`
- Intel Mac 10.13.6 用パッケージ: `build/intel_mac_1013_package/`

各フォルダには配布用 `.app`、`Install_*.app`、受け手向け `README.md` を置く。
インストーラは同じフォルダ内の本体 `.app` を Desktop にコピーし、`com.apple.quarantine` を外して起動する。

> macOS 10.13.6 向け `x86_64_1013_py312` ビルドでは、互換性回避のため `app_1013.py` を使う。
> `Export CSV` ボタンの非表示と MSC ログテーブルのヘッダ固定は、この 10.13 向け専用実装で切り替えている。

### 起動トラブル時のログ確認

- Finder から `.app` が即終了した場合は `~/Library/Logs/MSC_MTC_Viewer/launch.log` を確認する
- ターミナルから直接起動して標準エラーも確認できる

```bash
dist/MSC_MTC_Viewer_x86_64.app/Contents/MacOS/MSC_MTC_Viewer_x86_64
dist/MSC_MTC_Viewer_x86_64_1013_py312.app/Contents/MacOS/MSC_MTC_Viewer_x86_64_1013_py312
```

---

## ファイル構成

```
msc_mtc_viewer/
├── app.py            # 標準ビルド用メインアプリ
├── app_1013.py       # macOS 10.13.6 用ビルド専用エントリーポイント
├── decoder.py        # MSC バイト列デコード（純粋関数、rtmidi 依存なし）
├── midi_receiver.py  # python-rtmidi ポート管理 + スレッドセーフ Queue
├── persistence.py    # 接続ポートの保存・読み込み（JSON）
├── config.json       # アプリ設定（バージョン、ウィンドウサイズ等）
├── requirements.txt  # 依存パッケージ
├── pyproject.toml    # Ruff 設定
├── setup.sh          # venv 作成（--x86 / --x86-1013-py312 / --all）
├── build_app.py      # PyInstaller ビルドスクリプト（--arch arm64|x86_64|x86_64_1013_py312）
├── .venv/            # arm64 用 Python 環境
├── .venv_x86/        # x86_64 用 Python 環境（setup.sh --x86 で作成）
├── .venv_x86_1013_py312/ # macOS 10.13.6 向け x86_64 / Python 3.12 環境
├── build/            # 配布パッケージと配布メモ
├── CLAUDE.md         # 開発者向けドキュメント
└── README.md         # 本ファイル
```

---

## 設定ファイル

```
~/Library/Application Support/MSC_MTC_Viewer/settings.json
```

前回接続していたポート名・UI 設定を保存する。Finder から直接確認・編集可能。

```json
{
  "saved_ports": ["IAC ドライバ Bus 1"],
  "raw_hex_visible": true,
  "max_display_rows": 500
}
```

---

## 依存パッケージ

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| flask | 3.1.3 | HTTP サーバー / SSE |
| pywebview | 6.1 | macOS ネイティブウィンドウ（WKWebView） |
| python-rtmidi | 1.5.8 | MIDI 入力受信 |
| pyinstaller | 6.19.0 | .app バンドル生成 |
| ruff | 0.15.7 | Lint / フォーマット |

---

## MSC メッセージ仕様

MIDI Show Control 1.1 仕様に準拠。

```
F0 7F <device_ID> 02 <command_format> <command> [data] F7
```

仕様の詳細は `../midi_monitor_decorder/docs/MIDI1.0_MSC.md` を参照。
