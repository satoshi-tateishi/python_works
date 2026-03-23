# MIDI_MONITOR_DECODER.md

## 概要

MIDI Monitor（.mmon）で保存されたログファイルから、MSC（MIDI Show Control）イベントのみを抽出し、
人間が読める形式にデコードしてCSVとして出力するツールを実装する。

対象用途は音響・照明現場でのログ解析であり、
「あとから見て意味が一発でわかるログ」を生成することを目的とする。

---

## 入力

* ファイル形式: `.mmon`（MIDI Monitorの保存ファイル）
* 内部形式:

  * Apple Binary Property List（bplist）
  * 内部にNSKeyedArchive形式でイベント配列が含まれる

---

## 出力

CSVファイル

### カラム

* `time` : イベント時刻（文字列）
* `raw_hex` : MIDI生データ（スペース区切りの16進）
* `decoded` : 人間向けデコード結果

### 出力例

```csv
time,raw_hex,decoded
00:00:01.234,F0 7F 7F 02 7F 01 32 31 2E 35 30 30 F7,MSC GO cue=21.500
00:00:02.108,F0 7F 7F 02 7F 02 F7,MSC STOP
```

---

## 処理フロー

1. `.mmon` ファイルを読み込む
2. plist をデコード
3. イベント配列を取得
4. 各イベントから以下を取得

   * timestamp
   * messageData（バイト列）
5. SysExイベントのみ対象とする
6. MSCフォーマットに一致するもののみ抽出
7. デコード
8. CSV出力

---

## MSC判定条件

以下の条件をすべて満たすものをMSCとする

* 先頭が `F0`
* 2バイト目が `7F`
* 4バイト目が `02`
* 最後が `F7`

形式:

```
F0 7F <device_id> 02 <command_format> <command> <data> F7
```

---

## command_format

| 値  | 意味               |
| -- | ---------------- |
| 01 | General Lighting |
| 02 | Moving Light     |
| 7F | All Types        |

※ decoded文字列には表示しなくてもよい（任意）

---

## command

| 値  | 意味     |
| -- | ------ |
| 01 | GO     |
| 02 | STOP   |
| 03 | RESUME |
| 06 | SET    |
| 07 | FIRE   |

未知のcommandは無視（出力しない）

---

## デコード仕様

### 共通

```
decoded = "MSC <COMMAND>"
```

例:

* MSC GO
* MSC STOP

---

## GO (command = 01)

data部分を解析する

### データ仕様

* ASCIIエンコードされた文字列（16進）
* 数字: `30-39`
* 小数点: `2E` → `.`
* 区切り: `00`

---

## デコード手順（GO）

1. data部分を抽出
2. `00` で分割
3. 各ブロックをASCII変換

---

## ASCII変換ルール

| HEX   | 文字  |
| ----- | --- |
| 30-39 | 0-9 |
| 2E    | .   |

それ以外の値が含まれる場合は不正データとして除外

---

## 分解ロジック

### ケース1: 要素数 = 1

```
cueのみ
```

出力:

```
MSC GO cue=<cue>
```

---

### ケース2: 要素数 = 2

```
cue + exec.page
```

出力:

```
MSC GO cue=<cue> exec.page=<value>
```

---

### ケース3: 要素数 >= 3

```
cue + exec + page
```

出力:

```
MSC GO cue=<cue> exec=<exec> page=<page>
```

---

## STOP / RESUME / SET / FIRE

dataは解析しない

出力:

```
MSC STOP
MSC RESUME
MSC SET
MSC FIRE
```

---

## 除外条件

以下はすべて無視（CSVに出力しない）

* SysEx以外
* MSC形式でない
* 未知のcommand
* dataに不正な値が含まれる（GOの場合）
* 空データ

---

## 実装要件

### 必須

* Pythonで実装
* 単一ファイルで動作
* CLI対応

```
python decoder.py input.mmon output.csv
```

---

### 使用ライブラリ

* `plistlib`
* `csv`
* `argparse`

---

## 出力仕様

* UTF-8
* 改行コード: LF
* ヘッダ付き

---

## 優先順位

### 優先度 高

* MSC GOの正確なデコード
* 安定した抽出

### 優先度 中

* STOP / RESUME対応

### 優先度 低

* command_format表示
* その他MSC拡張

---

## 非対応（明示）

以下は実装しない

* `.mmon`以外の形式
* リアルタイム処理
* GUI
* SysEx全般の汎用解析
* 非ASCII data解析

---

## 今後の拡張（参考）

* unknownログ別出力
* JSON出力
* リアルタイム監視
* Ableton / QLab連携

---

## 完了条件

以下を満たすこと

* `.mmon`からMSCイベントが抽出できる
* GOのcueが正しく表示される
* CSVがExcelで読める
* 不正データでクラッシュしない

---
