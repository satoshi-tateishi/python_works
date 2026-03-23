#!/usr/bin/env python3
"""
MIDI Monitor (.mmon) MSC Decoder
.mmonファイルからMSC（MIDI Show Control）イベントを抽出してCSV出力する
Usage: python decoder.py input.mmon output.csv
"""

import argparse
import csv
import datetime
import plistlib
import sys

MAC_EPOCH_OFFSET = 978307200  # 2001-01-01 UTC → Unix epoch差分（秒）

MSC_COMMANDS = {
    0x01: "GO",
    0x02: "STOP",
    0x03: "RESUME",
    0x06: "SET",
    0x07: "FIRE",
}


def _resolve_objects(inner_plist):
    """NSKeyedArchive の $objects からUID解決用クロージャを返す"""
    objects = inner_plist["$objects"]

    def resolve(uid):
        return objects[uid.data]

    return resolve, objects


def _load_inner_plist(mmon_path=None, raw_bytes=None):
    """外側plistを読み込み、messageData の内側plistを返す"""
    if raw_bytes is not None:
        outer = plistlib.loads(raw_bytes)
    else:
        with open(mmon_path, "rb") as f:
            outer = plistlib.load(f)
    return plistlib.loads(outer["messageData"])


def _is_msc(status_byte, data_bytes, eox):
    """MSC判定: SysExかつ MSC形式かつ F7終端"""
    if status_byte != 0xF0:
        return False
    if not eox:
        return False
    if len(data_bytes) < 5:
        return False
    if data_bytes[0] != 0x7F:
        return False
    if data_bytes[2] != 0x02:
        return False
    return True


def _decode_ascii_field(raw_bytes):
    """
    ASCIIエンコードされた数字・小数点バイト列を文字列に変換。
    不正な値が含まれる場合は None を返す。
    """
    result = []
    for b in raw_bytes:
        if 0x30 <= b <= 0x39:
            result.append(chr(b))
        elif b == 0x2E:
            result.append(".")
        else:
            return None
    return "".join(result)


def _parse_go_data(data_bytes):
    """
    GOコマンドのdataバイト列を解析して (cue, page) を返す。

    MSC 1.1 仕様に準拠したフィールド構造:
      フィールド0: Q_number（Cue No.）  ※オプション
      フィールド1: Q_list（ページ/エグゼキュータ番号）  ※オプション
      フィールド2: Q_path（キューパス）  ※無視

    Q_number を省略したベアGO（F0 7F .. 02 .. 01 F7）も有効で ("", "") を返す。
    フィールドに不正なバイトが含まれる場合のみ None を返す。
    """
    go_data = data_bytes[5:]

    # 0x00 でフィールドを分割（空フィールドも位置を保持するためフィルタしない）
    segments = []
    current = []
    for b in go_data:
        if b == 0x00:
            segments.append(bytes(current))
            current = []
        else:
            current.append(b)
    if current:
        segments.append(bytes(current))

    # Q_number (segments[0]) と Q_list (segments[1]) を取り出す
    # 空フィールドは "" として扱う（ベアGOや省略フィールドを許容）
    cue = ""
    page = ""

    if len(segments) >= 1 and segments[0]:
        val = _decode_ascii_field(segments[0])
        if val is None:
            return None  # 不正バイト
        cue = val

    if len(segments) >= 2 and segments[1]:
        val = _decode_ascii_field(segments[1])
        if val is None:
            return None  # 不正バイト
        page = val

    return cue, page


def _parse_message(msg, resolve):
    """
    1メッセージをrow dictに変換する。
    MSC以外・不正データは None を返す。
    """
    status_byte = msg.get("statusByte", 0)
    eox = msg.get("wasReceivedWithEOX", False)
    clock_ts = msg.get("clockTimeStamp", 0.0)
    data_uid = msg.get("data")

    if data_uid is None:
        return None

    data_bytes = resolve(data_uid)
    if not isinstance(data_bytes, bytes):
        return None

    if not _is_msc(status_byte, data_bytes, eox):
        return None

    command_byte = data_bytes[4]
    command_name = MSC_COMMANDS.get(command_byte)
    if command_name is None:
        return None

    cue = ""
    page = ""
    if command_name == "GO":
        result = _parse_go_data(data_bytes)
        if result is None:
            return None  # 不正データ
        cue, page = result

    # 時刻変換（ローカルタイムゾーン基準。.mmon 作成環境と異なる場合は時刻がずれる）
    unix_ts = clock_ts + MAC_EPOCH_OFFSET
    dt = datetime.datetime.fromtimestamp(unix_ts)
    timestamp = dt.strftime("%H時%M分%S秒")
    date_str = dt.strftime("%Y-%m-%d")
    iso_str = dt.strftime("%Y-%m-%dT%H:%M:%S")

    # raw_hex: F0 + body + F7
    full_bytes = bytes([0xF0]) + data_bytes + bytes([0xF7])
    raw_hex = " ".join(f"{b:02X}" for b in full_bytes)

    return {
        "timestamp": timestamp,
        "date": date_str,
        "datetime_iso": iso_str,
        "msc": "MSC",
        "command": command_name,
        "page": page,
        "cue": cue,
        "raw_hex": raw_hex,
    }


def _collect_rows(root_array, resolve):
    """NSKeyedArchive の root 配列から MSC row リストを返す"""
    rows = []
    for uid in root_array["NS.objects"]:
        try:
            msg = resolve(uid)
            row = _parse_message(msg, resolve)
        except (IndexError, KeyError, TypeError):
            continue  # 壊れたエントリはスキップ
        if row is not None:
            rows.append(row)
    return rows


def decode_mmon_bytes(raw_bytes):
    """
    .mmon ファイルのバイナリデータからMSCイベントのrowリストを返す。
    app.py から利用する。
    """
    inner = _load_inner_plist(raw_bytes=raw_bytes)
    resolve, objects = _resolve_objects(inner)
    return _collect_rows(resolve(inner["$top"]["root"]), resolve)


def _process_to_csv(mmon_path, csv_path):
    """CLIからCSVを出力する"""
    inner = _load_inner_plist(mmon_path=mmon_path)
    resolve, objects = _resolve_objects(inner)
    rows = _collect_rows(resolve(inner["$top"]["root"]), resolve)

    fieldnames = [
        "タイムスタンプ",
        "date",
        "datetime_iso",
        "MSC",
        "コマンド",
        "page",
        "Cue No.",
        "raw_hex",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "タイムスタンプ": row["timestamp"],
                    "date": row["date"],
                    "datetime_iso": row["datetime_iso"],
                    "MSC": row["msc"],
                    "コマンド": row["command"],
                    "page": row["page"],
                    "Cue No.": row["cue"],
                    "raw_hex": row["raw_hex"],
                }
            )
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="MIDI Monitor (.mmon) MSC Decoder")
    parser.add_argument("input", help="入力ファイル (.mmon)")
    parser.add_argument("output", help="出力ファイル (.csv)")
    args = parser.parse_args()

    try:
        count = _process_to_csv(args.input, args.output)
        print(f"{count} MSCイベントを出力しました → {args.output}")
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {args.input}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
