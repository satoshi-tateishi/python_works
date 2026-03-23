# MIDI_MONITOR_DECODER.md

## 概要

MIDI Monitor（.mmon）で保存されたログファイルから、MSC（MIDI Show Control）イベントのみを抽出し、
人間が読める形式にデコードして表示・CSV出力するツール。

対象用途は音響・照明現場でのログ解析。

---

## アーキテクチャ

| ファイル | 役割 |
|---|---|
| `decoder.py` | .mmon パース・MSCデコードのコアロジック。CLIとしても動作 |
| `app.py` | Flask サーバー（スレッド）+ pywebview ネイティブウィンドウ GUI |
| `build_app.py` | PyInstaller で `dist/MSC Decoder.app` を生成 |
| `config.json` | バージョン・ポート・ウィンドウサイズ等の設定を一元管理 |

### 動作モード

**GUIアプリ（主用途）**

macOS ネイティブウィンドウ。.mmon ファイルをドラッグ＆ドロップまたはクリックで選択すると、
MSCイベントの一覧テーブルをリアルタイム表示する。

**CLI**

```bash
python decoder.py input.mmon output.csv
```

---

## 入力

* ファイル形式: `.mmon`（MIDI Monitorの保存ファイル）
* 内部形式:
  * Apple Binary Property List（bplist）外側
  * 内部に NSKeyedArchive 形式でイベント配列（`messageData` キー）

---

## 出力

### GUIテーブル（カラム）

| カラム | 内容 |
|---|---|
| タイムスタンプ | イベント時刻（ローカル時刻、`HH時MM分SS秒` 形式） |
| MSC | 固定値 `"MSC"` |
| コマンド | `GO` / `STOP` / `RESUME` / `SET` / `FIRE` |
| page | Q_list（キューリスト番号。照明ではエグゼキュータ/ページに相当） |
| Cue No. | Q_number（キュー番号） |

### CSVファイル（カラム）

| カラム | 内容 |
|---|---|
| タイムスタンプ | 表示用時刻文字列 |
| date | 日付（`YYYY-MM-DD`） |
| datetime_iso | ISO 8601形式（`YYYY-MM-DDTHH:MM:SS`） |
| MSC | 固定値 `"MSC"` |
| コマンド | コマンド名 |
| page | Q_list |
| Cue No. | Q_number |
| raw_hex | 生データ（F0 から F7 までスペース区切り16進） |

### 出力例

```csv
タイムスタンプ,date,datetime_iso,MSC,コマンド,page,Cue No.,raw_hex
21時52分11秒,2026-03-23,2026-03-23T21:52:11,MSC,GO,1,0.7,F0 7F 01 02 7F 01 30 2E 37 00 31 F7
21時52分15秒,2026-03-23,2026-03-23T21:52:15,MSC,STOP,,,F0 7F 01 02 7F 02 F7
```

---

## .mmon ファイル構造

```
.mmon（Apple Binary plist）
└── messageData: <bytes>
    └── NSKeyedArchive（内側 plist）
        └── $top.root → NS.objects[]
            └── 各メッセージ dict
                ├── statusByte: int         (0xF0 = SysEx)
                ├── wasReceivedWithEOX: bool (F7終端あり)
                ├── clockTimeStamp: float   (Mac参照時刻, 2001-01-01 UTC基準)
                └── data: <bytes>           (F0/F7を除いたボディ)
```

**時刻変換**: `unix_ts = clockTimeStamp + 978307200`

---

## MSC判定条件

以下の条件をすべて満たすものをMSCとする

* `statusByte == 0xF0`（SysEx）
* `wasReceivedWithEOX == True`（F7終端あり）
* `data[0] == 0x7F`（Real Time）
* `data[2] == 0x02`（MSC）
* データ長 5バイト以上

形式:

```
F0 7F <device_id> 02 <command_format> <command> [<data>] F7
     ↑data[0]        ↑data[2]         ↑data[3]  ↑data[4]
```

---

## command_format（data[3]）

| 値 | 意味 |
|---|---|
| 01 | General Lighting |
| 02 | Moving Light |
| 7F | All Types |

デコード結果には表示しない。

---

## コマンド（data[4]）

| 値 | コマンド名 |
|---|---|
| 01 | GO |
| 02 | STOP |
| 03 | RESUME |
| 06 | SET |
| 07 | FIRE |

未知のコマンドは無視（出力しない）。

---

## MSC 1.1 GOコマンド データフィールド

```
F0 7F <device_ID> 02 <command_format> 01 [<Q_number> 00] [<Q_list> 00] [<Q_path>] F7
```

| MSC 1.1 正式名 | row dict キー | 説明 |
|---|---|---|
| Q_number | `"cue"` | キュー番号（オプション、省略時は次のキューをGO） |
| Q_list | `"page"` | キューリスト番号（照明ではエグゼキュータ/ページに相当） |
| Q_path | *(無視)* | キューパス（ファイルパス相当、表示不要） |

* フィールドは `0x00` で区切られ、位置が意味を持つ（空フィールドも位置を保持）
* Q_number を省略したベアGO（`F0 7F .. 02 .. 01 F7`）は MSC 1.1 の有効コマンド
  → 「次のキューをGO」の意味。`cue=""`, `page=""` として記録される

### フィールドエンコード

| HEX | 文字 |
|---|---|
| 30–39 | 0–9 |
| 2E | . |

それ以外のバイトが含まれる場合は不正データとして除外。

---

## 除外条件

以下はすべて無視（出力しない）

* SysEx以外のMIDIメッセージ
* F7終端なし
* MSC形式でない（data[0]≠0x7F、data[2]≠0x02、データ長不足）
* 未知のコマンド
* GOの data フィールドに不正なバイトが含まれる

---

## row dict 構造（内部）

```python
{
    "timestamp":    "21時52分11秒",
    "date":         "2026-03-23",
    "datetime_iso": "2026-03-23T21:52:11",
    "msc":          "MSC",
    "command":      "GO",
    "page":         "1",      # Q_list。なければ ""
    "cue":          "0.7",    # Q_number。なければ ""
    "raw_hex":      "F0 7F 01 02 7F 01 ...",
}
```

---

## 完了条件（達成済み）

* `.mmon` から MSCイベントが抽出できる
* GOの Cue No. / page が正しく表示される
* ベアGO（Q_number省略）も正常にデコードできる
* CSVがExcelで読める（UTF-8、LF、ヘッダ付き）
* 不正データでクラッシュしない
* macOS .app としてビルドできる（universal2: Intel + Apple Silicon 両対応）

---

## 今後の拡張（参考）

* unknown イベント別出力
* JSON出力
* リアルタイム監視
* QLab / EOS 連携
