"""
MIDI ポート管理モジュール
python-rtmidi を使ってライブ MIDI 受信を行う。
スレッドセーフな Queue 経由でメッセージを app.py に渡す。
"""

import queue

import rtmidi

# ---------------------------------------------------------------------------
# モジュールレベルの状態
# ---------------------------------------------------------------------------
_inputs: dict[str, rtmidi.MidiIn] = {}
_message_queue: queue.Queue = queue.Queue(maxsize=2000)


# ---------------------------------------------------------------------------
# ポート名エンコード修正
# ---------------------------------------------------------------------------
def _fix_port_name(name: str) -> str:
    """
    python-rtmidi が CoreMIDI の UTF-8 文字列を Mac Roman として誤デコードする問題を修正する。
    例: ド(UTF-8: E3 83 89) → Mac Roman 誤読 → „Éâ → 本関数で ド に戻す。

    修正手順:
        1. Mac Roman として encode → 元の UTF-8 バイト列を復元
        2. UTF-8 として decode → 正しい Unicode 文字列
    失敗した場合（すでに正しい文字列、または別エンコード）はそのまま返す。
    """
    try:
        return name.encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


# ---------------------------------------------------------------------------
# ポート一覧
# ---------------------------------------------------------------------------
def get_available_ports() -> list[str]:
    """現在利用可能な MIDI 入力ポート名の一覧を返す。"""
    tmp = rtmidi.MidiIn()
    ports = [_fix_port_name(p) for p in tmp.get_ports()]
    del tmp
    return ports


def get_connected_ports() -> list[str]:
    """現在接続中のポート名の一覧を返す。"""
    return list(_inputs.keys())


# ---------------------------------------------------------------------------
# ポート接続 / 切断
# ---------------------------------------------------------------------------
def connect_port(port_name: str) -> bool:
    """
    指定したポート名に接続する。
    既に接続済みの場合は True を返してスキップする。
    ポートが見つからない場合は False を返す。
    """
    if port_name in _inputs:
        return True

    midi_in = rtmidi.MidiIn()
    # get_ports() も同様に文字コード修正を適用してブラウザ側の名前と一致させる
    ports = [_fix_port_name(p) for p in midi_in.get_ports()]
    if port_name not in ports:
        del midi_in
        return False

    index = ports.index(port_name)
    midi_in.open_port(index)
    # SysEx(F0) と MTC Quarter Frame(F1) を受信可能にする。
    # timing=False: RtMidi は 0xF1(MTC QF) も timing フラグで制御するため False が必須。
    # active_sense=True: Active Sensing(FE) は無視。
    midi_in.ignore_types(sysex=False, timing=False, active_sense=True)
    midi_in.set_callback(_make_callback(port_name))
    _inputs[port_name] = midi_in
    return True


def disconnect_port(port_name: str) -> None:
    """指定したポートとの接続を閉じる。"""
    midi_in = _inputs.pop(port_name, None)
    if midi_in is not None:
        midi_in.close_port()
        del midi_in


def disconnect_all() -> None:
    """すべての接続中ポートを切断する。"""
    for name in list(_inputs.keys()):
        disconnect_port(name)


# ---------------------------------------------------------------------------
# コールバック
# ---------------------------------------------------------------------------
def _make_callback(port_name: str):
    """port_name をキャプチャした rtmidi コールバック関数を返す。"""

    def callback(message, _data=None):
        raw = message[0]  # list[int]
        if not raw:
            return
        # SysEx (F0) と MTC Quarter Frame (F1) のみキュー投入
        if raw[0] == 0xF1:
            try:
                _message_queue.put_nowait({"type": "qf", "port": port_name, "raw": raw})
            except queue.Full:
                pass
        elif raw[0] == 0xF0:
            try:
                _message_queue.put_nowait({"type": "sysex", "port": port_name, "raw": raw})
            except queue.Full:
                pass

    return callback


# ---------------------------------------------------------------------------
# キュー取り出し
# ---------------------------------------------------------------------------
def get_next_message(timeout: float = 0.5) -> dict | None:
    """
    次のメッセージをブロッキングで取り出す。
    timeout 秒待っても来なければ None を返す。
    各要素: {"type": "sysex"|"qf", "port": str, "raw": list[int]}
    """
    try:
        return _message_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def drain_queue() -> list[dict]:
    """
    Queue に溜まったすべてのメッセージを非ブロッキングで取り出して返す。
    /api/clear などで使用。
    """
    items = []
    while True:
        try:
            items.append(_message_queue.get_nowait())
        except queue.Empty:
            break
    return items
