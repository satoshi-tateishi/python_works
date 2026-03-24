"""
MSC バイト列デコードモジュール
受信した生の SysEx バイト列を MSC メッセージに解析する純粋関数モジュール。
rtmidi への依存なし。
"""

# ---------------------------------------------------------------------------
# MSC command_format テーブル
# ---------------------------------------------------------------------------
MSC_FORMATS: dict[int, str] = {
    0x01: "Lighting",
    0x02: "Moving Lights",
    0x03: "Colour Changers",
    0x04: "Strobes",
    0x05: "Lasers",
    0x06: "Chasers",
    0x10: "Sound",
    0x11: "Music",
    0x12: "CD Players",
    0x13: "EPROM Playback",
    0x14: "Audio Tape Machines",
    0x15: "Intercoms",
    0x16: "Amplifiers",
    0x17: "Audio Effects Devices",
    0x18: "Equalizers",
    0x20: "Machinery",
    0x21: "Rigging",
    0x22: "Flys",
    0x23: "Lifts",
    0x24: "Turntables",
    0x25: "Trusses",
    0x26: "Robots",
    0x27: "Animation",
    0x28: "Floats",
    0x29: "Breakaways",
    0x2A: "Barges",
    0x30: "Video",
    0x31: "Video Tape Machines",
    0x32: "Video Cassette Machines",
    0x33: "Video Disc Players",
    0x34: "Video Switchers",
    0x35: "Video Effects",
    0x36: "Video Character Generators",
    0x37: "Video Still Stores",
    0x38: "Video Monitors",
    0x40: "Projection",
    0x41: "Film Projectors",
    0x42: "Slide Projectors",
    0x43: "Video Projectors",
    0x44: "Dissolvers",
    0x45: "Shutter Controls",
    0x50: "Process Control",
    0x51: "Hydraulic Oil",
    0x52: "H2O",
    0x53: "CO2",
    0x54: "Compressed Air",
    0x55: "Natural Gas",
    0x56: "Fog",
    0x57: "Smoke",
    0x58: "Cracked Haze",
    0x60: "Pyro",
    0x61: "Fireworks",
    0x62: "Explosions",
    0x63: "Flame",
    0x64: "Smoke Pots",
    0x7F: "All Types",
}

# ---------------------------------------------------------------------------
# MSC command テーブル
# ---------------------------------------------------------------------------
MSC_COMMANDS: dict[int, str] = {
    0x01: "GO",
    0x02: "STOP",
    0x03: "RESUME",
    0x04: "TIMED_GO",
    0x05: "LOAD",
    0x06: "SET",
    0x07: "FIRE",
    0x08: "ALL_OFF",
    0x09: "RESTORE",
    0x0A: "RESET",
    0x0B: "GO_OFF",
    0x10: "GO_JAM_CLOCK",
    0x11: "STANDBY+",
    0x12: "STANDBY-",
    0x13: "SEQUENCE+",
    0x14: "SEQUENCE-",
    0x15: "START_CLOCK",
    0x16: "STOP_CLOCK",
    0x17: "ZERO_CLOCK",
    0x18: "SET_CLOCK",
    0x19: "MTC_CHASE_ON",
    0x1A: "MTC_CHASE_OFF",
    0x1B: "OPEN_CUE_LIST",
    0x1C: "CLOSE_CUE_LIST",
    0x1D: "OPEN_CUE_PATH",
    0x1E: "CLOSE_CUE_PATH",
    # 2-Phase Commit
    0x20: "STANDBY_2PC",
    0x21: "STANDING_BY",
    0x22: "GO_2PC",
    0x23: "COMPLETE",
    0x24: "CANCEL",
    0x25: "CANCELLED",
    0x26: "ABORT",
}


def _format_device_id(dev_id: int) -> str:
    """device_ID バイトを表示文字列に変換する。"""
    if dev_id == 0x7F:
        return "ALL"
    if 0x70 <= dev_id <= 0x7E:
        return f"GRP_{dev_id - 0x70 + 1}"
    return str(dev_id)


def _decode_ascii_field(raw: bytes) -> str | None:
    """
    MSC の ASCII フィールド（Q_number / Q_list / Q_path）をデコードする。
    使用できる文字: 0x30–0x39（数字）, 0x2E（小数点）
    空バイト列の場合は "" を返す。
    不正な文字が含まれる場合は None を返す。
    """
    if len(raw) == 0:
        return ""
    result = []
    for b in raw:
        if 0x30 <= b <= 0x39 or b == 0x2E:
            result.append(chr(b))
        else:
            return None
    return "".join(result)


def _parse_cue_data(data_tail: bytes) -> tuple[str, str]:
    """
    GO / STOP / RESUME / TIMED_GO / LOAD / GO_OFF の後続データを解析する。
    <Q_number> 00 <Q_list> 00 <Q_path> F7 の形式。
    F7 は呼び出し前に除去済みであること。

    Returns:
        (q_number, q_list) のタプル。フィールドがない場合は ""。
    """
    fields: list[bytes] = []
    current: list[int] = []
    for b in data_tail:
        if b == 0x00:
            fields.append(bytes(current))
            current = []
        else:
            current.append(b)
    if current:
        fields.append(bytes(current))

    q_number = ""
    q_list = ""

    if len(fields) >= 1:
        decoded = _decode_ascii_field(fields[0])
        q_number = decoded if decoded is not None else ""
    if len(fields) >= 2:
        decoded = _decode_ascii_field(fields[1])
        q_list = decoded if decoded is not None else ""

    return q_number, q_list


def decode_msc_bytes(raw_bytes: list[int]) -> dict | None:
    """
    生の SysEx バイト列（F0 / F7 を含む）を MSC メッセージにデコードする。

    MSC フォーマット:
        F0 7F <device_ID> 02 <command_format> <command> [data] F7

    Args:
        raw_bytes: int のリスト（rtmidi のコールバックから受け取った message[0]）

    Returns:
        デコード結果の dict。MSC でなければ None。
        {
            "device_id": str,
            "cmd_format": str,
            "command": str,
            "q_number": str,
            "q_list": str,
            "raw_hex": str,
        }
    """
    # 最小長チェック: F0 7F devID 02 cmdFmt cmd F7 = 7 バイト
    if len(raw_bytes) < 7:
        return None
    if raw_bytes[0] != 0xF0:
        return None
    if raw_bytes[-1] != 0xF7:
        return None
    # Universal Real-Time SysEx
    if raw_bytes[1] != 0x7F:
        return None
    # MSC Sub-ID #1
    if raw_bytes[3] != 0x02:
        return None

    dev_id_byte = raw_bytes[2]
    cmd_fmt_byte = raw_bytes[4]
    cmd_byte = raw_bytes[5]

    # data 部分（cmd の後から F7 の前まで）
    data_tail = bytes(raw_bytes[6:-1])

    device_id = _format_device_id(dev_id_byte)
    cmd_format = MSC_FORMATS.get(cmd_fmt_byte, f"FMT_0x{cmd_fmt_byte:02X}")
    command = MSC_COMMANDS.get(cmd_byte, f"CMD_0x{cmd_byte:02X}")

    # Q_number / Q_list を持つコマンド
    cue_commands = {0x01, 0x02, 0x03, 0x04, 0x05, 0x0B}
    if cmd_byte in cue_commands and len(data_tail) > 0:
        q_number, q_list = _parse_cue_data(data_tail)
    else:
        q_number, q_list = "", ""

    raw_hex = " ".join(f"{b:02X}" for b in raw_bytes)

    return {
        "device_id": device_id,
        "cmd_format": cmd_format,
        "command": command,
        "q_number": q_number,
        "q_list": q_list,
        "raw_hex": raw_hex,
    }
