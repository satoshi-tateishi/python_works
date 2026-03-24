# MIDI MSC Monitor

USB-MIDI インターフェースや IAC から受信した **MIDI Show Control (MSC)** メッセージをリアルタイムで解析・表示する macOS デスクトップアプリ。

## 対応環境

- macOS（Intel / Apple Silicon 両対応）
- Python 3.11 以上（ビルドには python.org 版 Python 3.13 推奨）

---

## 機能

### MIDI ポート管理
- 接続中の USB-MIDI インターフェースおよび IAC をチェックボックスで複数選択可能
- 「再スキャン」ボタンでポート一覧を更新
- 前回使用したポートを起動時に自動接続（`~/Documents/MIDI MSC Monitor/settings.json` に保存）

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
| Raw Hex | 生バイト列（16進数） |

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

### ログ操作
- **クリア**: 表示中のログを消去
- **CSV エクスポート**: 表示中のログを `msc_log_YYYYMMDD_HHMMSS.csv` としてダウンロード
- **自動スクロール**: ON/OFF 切替。新着メッセージへ自動スクロールするかを制御
- 最大 500 行表示（超えると古い行から削除）

---

## セットアップ

```bash
# 初回のみ
bash setup.sh

# 起動
.venv/bin/python app.py
```

`setup.sh` は python.org 版 Python 3.13 を優先して使用する（universal2 ビルド用）。
見つからない場合はシステムの `python3` にフォールバックする（arm64 専用ビルドになる）。

---

## macOS .app ビルド

```bash
.venv/bin/python build_app.py
```

`dist/MIDI MSC Monitor.app` が生成される。Intel / Apple Silicon の両アーキテクチャに対応した universal2 バイナリ。

> ビルドには python.org 版 Python 3.13 と Xcode Command Line Tools が必要。

---

## ファイル構成

```
msc_mtc_viewer/
├── app.py            # Flask サーバー + pywebview ウィンドウ + HTML/JS UI（埋め込み）
├── decoder.py        # MSC バイト列デコード（純粋関数、rtmidi 依存なし）
├── midi_receiver.py  # python-rtmidi ポート管理 + スレッドセーフ Queue
├── persistence.py    # 接続ポートの保存・読み込み（JSON）
├── config.json       # アプリ設定（バージョン、ウィンドウサイズ等）
├── requirements.txt  # 依存パッケージ
├── pyproject.toml    # Ruff 設定
├── setup.sh          # venv 作成 + pip install
├── build_app.py      # PyInstaller universal2 ビルドスクリプト
├── CLAUDE.md         # 開発者向けドキュメント
└── README.md         # 本ファイル
```

---

## 設定ファイル

```
~/Documents/MIDI MSC Monitor/settings.json
```

前回接続していたポート名を保存する。Finder から直接確認・編集可能。

```json
{
  "saved_ports": [
    "IAC ドライバ Bus 1"
  ]
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
