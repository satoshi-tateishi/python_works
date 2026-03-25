"""
MSC_MTC_Viewer — メインアプリケーション
Flask サーバー（バックグラウンドスレッド）+ pywebview ネイティブウィンドウ。
HTML/JS UI はこのファイルに埋め込み文字列として定義する。
"""

import csv
import datetime
import json
import os
import sys
import threading
import time
import traceback

import webview
from flask import Flask, Response, request

import decoder
import midi_receiver
import persistence

# ---------------------------------------------------------------------------
# 設定ロード
# ---------------------------------------------------------------------------
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _load_config() -> dict:
    path = os.path.join(_BASE, "config.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_config = _load_config()
APP_NAME = _config["app_name"]
FLASK_PORT = _config.get("port", 0)
WINDOW_WIDTH = _config.get("window_width", 1100)
WINDOW_HEIGHT = _config.get("window_height")
WINDOW_MAXIMIZE = _config.get("window_maximize", False)
WINDOW_MIN_WIDTH = _config.get("window_min_width", 980)
WINDOW_MIN_HEIGHT = _config.get("window_min_height", 400)
WINDOW_X = _config.get("window_x")
WINDOW_Y = _config.get("window_y")
EXPORT_DIR = _config.get("export_dir", "~/Downloads/MSC_MTC_Viewer_CSV")

persistence.init(_config.get("settings_dir", "~/Documents/MSC_MTC_Viewer"))

# ---------------------------------------------------------------------------
# ログバッファ（最大 500 件）
# ---------------------------------------------------------------------------
MAX_LOG_ROWS = _config.get("max_log_rows", 500)
_log_buffer: list[dict] = []
_log_lock = threading.Lock()

# ---------------------------------------------------------------------------
# MTC Quarter Frame ニブル蓄積バッファ
# ---------------------------------------------------------------------------
_qf_nibbles: list[int | None] = [None] * 8
_mtc_lock = threading.Lock()

# ---------------------------------------------------------------------------
# HTML をモジュールロード時に ASCII 安全に変換する
# 非ASCII文字を &#XXXX; 形式の XML 数値文字参照に置換することで、
# WKWebView の文字コード自動判定による文字化けを完全に回避する。
# ---------------------------------------------------------------------------
# (HTML_UI は後方で定義されるため、モジュール末尾で _HTML_UI_BYTES を設定する)
_HTML_UI_BYTES: bytes = b""

# ---------------------------------------------------------------------------
# Flask アプリ
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "msc-monitor-secret"


@app.route("/")
def index():
    return Response(_HTML_UI_BYTES, content_type="text/html")


@app.route("/api/ports")
def api_ports():
    available = midi_receiver.get_available_ports()
    connected = set(midi_receiver.get_connected_ports())
    ports = [{"name": n, "connected": n in connected} for n in available]
    # ensure_ascii=True（デフォルト）で \uXXXX エスケープ → 純粋 ASCII
    body = json.dumps({"ports": ports}).encode("ascii")
    return Response(body, content_type="application/json")


@app.route("/api/ports/connect", methods=["POST"])
def api_connect():
    data = request.get_json(force=True)
    port_name = data.get("port", "")
    ok = midi_receiver.connect_port(port_name)
    if ok:
        persistence.save_connected_ports(midi_receiver.get_connected_ports())
    return json.dumps({"ok": ok}), 200, {"Content-Type": "application/json"}


@app.route("/api/ports/disconnect", methods=["POST"])
def api_disconnect():
    data = request.get_json(force=True)
    port_name = data.get("port", "")
    midi_receiver.disconnect_port(port_name)
    persistence.save_connected_ports(midi_receiver.get_connected_ports())
    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}


@app.route("/api/events")
def api_events():
    """Server-Sent Events でリアルタイムにデコード済み MSC メッセージを配信する。"""

    def generate():
        while True:
            # ブロッキング取り出し（0.5s でタイムアウト → keepalive コメント送信）
            m = midi_receiver.get_next_message(timeout=0.5)
            if m is None:
                # SSE keepalive: プロキシや WebKit の接続タイムアウトを防ぐ
                yield ": keepalive\n\n"
                continue
            try:
                msg_type = m.get("type", "sysex")

                if msg_type == "qf":
                    # MTC Quarter Frame: ニブルを蓄積し、8つ揃ったらタイムコードを復元
                    data_byte = m["raw"][1]
                    nibble_type = (data_byte >> 4) & 0x07
                    nibble_val = data_byte & 0x0F
                    with _mtc_lock:
                        _qf_nibbles[nibble_type] = nibble_val
                        if all(n is not None for n in _qf_nibbles):
                            frames = ((_qf_nibbles[1] & 0x01) << 4) | _qf_nibbles[0]
                            seconds = ((_qf_nibbles[3] & 0x03) << 4) | _qf_nibbles[2]
                            minutes = ((_qf_nibbles[5] & 0x03) << 4) | _qf_nibbles[4]
                            hours = ((_qf_nibbles[7] & 0x01) << 4) | _qf_nibbles[6]
                            fps_code = (_qf_nibbles[7] >> 1) & 0x03
                            mtc_event = {
                                "event_type": "mtc",
                                "hours": hours,
                                "minutes": minutes,
                                "seconds": seconds,
                                "frames": frames,
                                "fps_code": fps_code,
                            }
                            yield f"data: {json.dumps(mtc_event)}\n\n"

                elif msg_type == "sysex":
                    raw = m["raw"]
                    # MTC Full Frame SysEx: F0 7F 7F 01 01 hr mn sc fr F7 (10 bytes)
                    if (
                        len(raw) == 10
                        and raw[0] == 0xF0
                        and raw[1] == 0x7F
                        and raw[3] == 0x01
                        and raw[4] == 0x01
                        and raw[9] == 0xF7
                    ):
                        hr_byte = raw[5]
                        fps_code = (hr_byte >> 5) & 0x03
                        hours = hr_byte & 0x1F
                        minutes = raw[6] & 0x3F
                        seconds = raw[7] & 0x3F
                        frames = raw[8] & 0x1F
                        mtc_event = {
                            "event_type": "mtc",
                            "hours": hours,
                            "minutes": minutes,
                            "seconds": seconds,
                            "frames": frames,
                            "fps_code": fps_code,
                        }
                        yield f"data: {json.dumps(mtc_event)}\n\n"
                    else:
                        # MSC デコード
                        row = decoder.decode_msc_bytes(raw)
                        if row is None:
                            continue
                        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        row["timestamp"] = ts
                        row["port"] = m["port"]
                        row["event_type"] = "msc"
                        with _log_lock:
                            _log_buffer.append(row)
                            if len(_log_buffer) > MAX_LOG_ROWS:
                                _log_buffer.pop(0)
                        yield f"data: {json.dumps(row)}\n\n"

            except Exception:
                # generator が死なないよう例外を握り潰す（デバッグ用にトレースは出力）
                traceback.print_exc()
                continue

    return Response(
        generate(),
        content_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/clear", methods=["POST"])
def api_clear():
    with _log_lock:
        _log_buffer.clear()
    # Queue も空にする
    midi_receiver.drain_queue()
    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}


@app.route("/api/export", methods=["POST"])
def api_export():
    """ログバッファを ~/Downloads/ に CSV として保存する。"""
    with _log_lock:
        rows = list(_log_buffer)

    filename = datetime.datetime.now().strftime("msc_log_%Y%m%d_%H%M%S.csv")
    export_dir = os.path.expanduser(EXPORT_DIR)
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, filename)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Timestamp", "Port", "Device ID", "Format", "Command", "Q_number", "Q_list", "Raw Hex"]
        )
        for r in rows:
            writer.writerow(
                [
                    r.get("timestamp", ""),
                    r.get("port", ""),
                    r.get("device_id", ""),
                    r.get("cmd_format", ""),
                    r.get("command", ""),
                    r.get("q_number", ""),
                    r.get("q_list", ""),
                    r.get("raw_hex", ""),
                ]
            )

    body = json.dumps({"ok": True, "filename": filename}).encode("ascii")
    return Response(body, content_type="application/json")


@app.route("/api/logs")
def api_logs():
    """ログバッファの末尾 limit 件を返す。"""
    try:
        limit = int(request.args.get("limit", 500))
    except (ValueError, TypeError):
        limit = 500
    with _log_lock:
        rows = list(_log_buffer[-limit:])
    body = json.dumps({"rows": rows}).encode("ascii")
    return Response(body, content_type="application/json")


@app.route("/api/settings")
def api_settings():
    """UI 設定（Raw Hex 表示状態・最大表示件数など）を返す。"""
    body = json.dumps(
        {
            "raw_hex_visible": persistence.load_raw_hex_visible(),
            "max_display_rows": persistence.load_max_display_rows(),
        }
    ).encode("ascii")
    return Response(body, content_type="application/json")


@app.route("/api/settings/raw_hex_visible", methods=["POST"])
def api_save_raw_hex_visible():
    """Raw Hex 列の表示状態を保存する。"""
    data = request.get_json(force=True)
    persistence.save_raw_hex_visible(bool(data.get("visible", True)))
    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}


@app.route("/api/settings/max_display_rows", methods=["POST"])
def api_save_max_display_rows():
    """ログテーブルの最大表示件数を保存する。"""
    data = request.get_json(force=True)
    rows = int(data.get("rows", 500))
    if rows not in (500, 1000, 5000):
        rows = 500
    persistence.save_max_display_rows(rows)
    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Flask サーバー起動（動的ポート）
# ---------------------------------------------------------------------------
from werkzeug.serving import make_server  # noqa: E402

_server = None
_PORT = None
_port_ready = threading.Event()


def _start_flask():
    global _server, _PORT
    _server = make_server("127.0.0.1", FLASK_PORT, app, threaded=True)
    _PORT = _server.socket.getsockname()[1]
    print(f"Flask server: http://127.0.0.1:{_PORT}/", flush=True)
    _port_ready.set()
    _server.serve_forever()


def _wait_for_server(timeout=10.0):
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", _PORT), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Flask サーバーが起動しませんでした")


# ---------------------------------------------------------------------------
# HTML / JS UI（埋め込み）
# ---------------------------------------------------------------------------
HTML_UI = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MSC_MTC_Viewer</title>
<style>
  :root {
    --bg: #1a1a2e;
    --bg2: #16213e;
    --bg3: #0f3460;
    --accent: #a0c4ff;
    --text: #d0d8f0;
    --muted: #8090b0;
    --go: #6dbf8b;
    --stop: #ff8080;
    --other: #f0c040;
    --border: #2a3a5e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
    font-size: 13px;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  header {
    background: var(--bg3);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .main-content {
    flex: 1;
    display: flex;
    flex-direction: row;
    overflow: hidden;
  }
  .left-panel {
    flex: 1;
    min-width: 600px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .right-panel {
    width: 380px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border);
    overflow: hidden;
  }
  .header-left {
    flex: 1;
    min-width: 0;
    padding: 8px 16px;
    display: flex;
    align-items: center;
  }
  /* ---- MTC タイムコードビューワー ---- */
  .mtc-viewer {
    flex: 1;
    background: var(--bg);
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 8px 14px;
  }
  .mtc-tc {
    font-size: 48px;
    font-weight: 700;
    color: #444;
    letter-spacing: -1px;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .mtc-tc.active { color: #6dbf8b; }
  .mtc-fps {
    font-size: 13px;
    color: var(--muted);
    margin-top: 2px;
    letter-spacing: 1px;
  }
  /* ---- 最終受信 MSC 大型表示パネル ---- */
  .last-msc {
    flex: 1;
    background: var(--bg);
    display: flex;
    align-items: center;
    padding: 8px 14px;
    gap: 0;
    overflow: hidden;
  }
  @keyframes lm-flash {
    0%   { background: rgba(109, 191, 139, 0.9); }
    40%  { background: rgba(109, 191, 139, 0.6); }
    100% { background: var(--bg); }
  }
  .last-msc.flash { animation: lm-flash 0.8s ease-out; }
  .lm-left {
    width: 76px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 3px;
  }
  .lm-center {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 0;
  }
  .lm-right {
    width: 76px;
    flex-shrink: 0;
    display: flex;
    align-items: flex-end;
    justify-content: flex-end;
  }
  .lm-devid, .lm-list {
    font-size: 12px;
    color: var(--text);
    line-height: 1.4;
    white-space: nowrap;
  }
  .lm-command {
    font-size: 15px;
    font-weight: 500;
    color: var(--muted);
    letter-spacing: 0.5px;
    margin-bottom: 2px;
  }
  .lm-command.cmd-go   { color: var(--go); }
  .lm-command.cmd-stop { color: var(--stop); }
  .lm-command.cmd-other { color: var(--other); }
  .lm-qnumber {
    font-size: 68px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1;
    letter-spacing: -1px;
    white-space: nowrap;
  }
  .lm-format {
    font-size: 11px;
    color: var(--muted);
    text-align: right;
    white-space: nowrap;
  }
  /* ---- ポートドロップダウン ---- */
  .port-dropdown {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .port-panel {
    display: none;
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 100;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 4px;
    min-width: 240px;
    padding: 4px 0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  }
  .port-panel.open { display: block; }
  .port-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    cursor: pointer;
    user-select: none;
    transition: background 0.1s;
  }
  .port-item:hover { background: var(--bg3); }
  .port-item.connected { color: var(--go); }
  .port-item input[type=checkbox] { cursor: pointer; accent-color: var(--go); }
  .port-item label { cursor: pointer; font-size: 12px; }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-size: 12px;
    padding: 3px 10px;
    cursor: pointer;
    user-select: none;
    transition: border-color 0.15s, background 0.15s;
  }
  .btn:hover { border-color: var(--accent); background: #1a2d50; }
  .btn-rescan { color: var(--accent); }
  select.btn { padding: 3px 6px; }
  select.btn option { background: #16213e; }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .count-badge {
    margin-left: auto;
    color: var(--muted);
    font-size: 12px;
  }
  .search-input {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-size: 12px;
    padding: 3px 8px;
    outline: none;
    width: 160px;
  }
  .search-input:focus { border-color: var(--accent); }
  .search-input::placeholder { color: var(--muted); }
  tr.search-match td { background: #2a3f6f; }
  .autoscroll-btn.active { color: var(--go); border-color: var(--go); }
  .table-wrap {
    flex: 1;
    overflow: auto;
    padding: 0;
  }
  table {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
    white-space: nowrap;
    font-size: 12px;
  }
  thead {
    background: var(--bg3);
    position: sticky;
    top: 0;
    z-index: 10;
  }
  thead th {
    padding: 7px 10px;
    text-align: left;
    color: var(--accent);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
    letter-spacing: 0.3px;
  }
  tbody tr {
    background: var(--bg2);
    border-bottom: 1px solid #1e2e48;
    transition: background 0.1s;
  }
  tbody tr:hover { background: #1e3050; }
  tbody td {
    padding: 5px 10px;
    vertical-align: middle;
  }
  .td-ts { color: var(--muted); font-family: monospace; }
  .td-port { color: var(--text); max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
  .td-devid { font-family: monospace; color: var(--accent); }
  .cmd-go { color: var(--go); font-weight: 600; }
  .cmd-stop { color: var(--stop); font-weight: 600; }
  .cmd-other { color: var(--other); font-weight: 600; }
  .td-raw { font-family: monospace; color: #8888aa; font-size: 11px; }
  /* ---- Raw Hex 折りたたみ ---- */
  .raw-hex-hidden .th-raw { width: 0 !important; padding: 0; overflow: hidden; }
  .raw-hex-hidden .td-raw { padding: 0; overflow: hidden; }
  .raw-hex-hidden .left-panel  { flex: 0 0 730px; min-width: 0; }
  .raw-hex-hidden .right-panel { flex: 1; width: auto; min-width: 420px; }
  .raw-hex-hidden .mtc-tc { font-size: 64px; }
  .raw-hex-hidden .lm-qnumber { font-size: 96px; }
  .empty-msg {
    text-align: center;
    color: var(--muted);
    padding: 40px;
    font-size: 13px;
  }
  .clock-bar {
    flex-shrink: 0;
    background: var(--bg);
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 8px 0 10px;
    user-select: none;
  }
  .clock-time {
    display: flex;
    align-items: baseline;
    gap: 4px;
    line-height: 1;
    color: #7878cc;
  }
  .clock-hm {
    font-size: 72px;
    font-weight: 300;
    letter-spacing: -2px;
    font-variant-numeric: tabular-nums;
  }
  .clock-sec {
    font-size: 36px;
    font-weight: 300;
    font-variant-numeric: tabular-nums;
    color: #6060aa;
    margin-bottom: 4px;
  }
  .clock-date {
    font-size: 16px;
    color: #7878cc;
    letter-spacing: 0.5px;
    margin-top: 2px;
  }
</style>
</head>
<body>
<header>
  <div class="header-left">
    <div class="port-dropdown" id="port-dropdown">
      <button class="btn" id="port-toggle" onclick="togglePortDropdown()">
        ポート ▼ &nbsp;<span id="port-count-badge">--</span>
      </button>
      <div class="port-panel" id="port-panel">
        <div id="port-list"></div>
      </div>
    </div>
    <button class="btn btn-rescan" onclick="loadPorts()">再スキャン</button>
  </div>
</header>

<div class="main-content">
  <div class="left-panel">
    <div class="toolbar">
      <button class="btn" id="btn-clear" onclick="clearLog()">クリア</button>
      <button class="btn" id="btn-export" onclick="exportCsv()">CSV エクスポート</button>
      <button class="btn" id="btn-raw-hex" onclick="toggleRawHex()">Raw Hex</button>
      <button class="btn autoscroll-btn active" id="btn-autoscroll" onclick="toggleAutoScroll()">
        自動スクロール: ON
      </button>
      <select class="btn" id="sel-max-rows" onchange="changeMaxRows(parseInt(this.value))">
        <option value="500">500件</option>
        <option value="1000">1000件</option>
        <option value="5000">5000件</option>
      </select>
      <input type="text" class="search-input" id="search-input" autocomplete="off"
        placeholder="Q_number 検索..." oninput="onSearchInput(this.value)">
      <button class="btn" id="btn-search-clear" onclick="clearSearch()"
        style="display:none; padding:3px 7px;">&#10005;</button>
      <span id="search-count" style="display:none; color:var(--accent); font-size:12px;"></span>
      <span class="count-badge" id="count-badge">0 件</span>
    </div>
    <div class="table-wrap" id="table-wrap">
      <table id="msg-table">
        <thead>
          <tr>
            <th style="width:100px">時刻</th>
            <th style="width:160px">ポート</th>
            <th style="width:70px">Dev ID</th>
            <th style="width:130px">Format</th>
            <th style="width:110px">Command</th>
            <th style="width:80px">Q_number</th>
            <th style="width:60px">Q_list</th>
            <th class="th-raw" style="width:220px">Raw Hex</th>
            <th class="th-filler"></th>
          </tr>
        </thead>
        <tbody id="msg-tbody"></tbody>
      </table>
      <div class="empty-msg" id="empty-msg">MSC メッセージを待機中...</div>
    </div>
  </div>
  <div class="right-panel">
    <div class="last-msc" id="last-msc">
      <div class="lm-left">
        <div class="lm-devid" id="lm-devid"></div>
        <div class="lm-list"  id="lm-list"></div>
      </div>
      <div class="lm-center">
        <div class="lm-command" id="lm-command"></div>
        <div class="lm-qnumber" id="lm-qnumber">--</div>
      </div>
      <div class="lm-right">
        <div class="lm-format" id="lm-format"></div>
      </div>
    </div>
    <div class="mtc-viewer">
      <div class="mtc-tc" id="mtc-tc">--:--:--.--</div>
      <div class="mtc-fps" id="mtc-fps"></div>
    </div>
  </div>
</div>

<div class="clock-bar" id="clock-bar">
  <div class="clock-time">
    <span class="clock-hm" id="clock-hm">--:--</span>
    <span class="clock-sec" id="clock-sec">--</span>
  </div>
  <div class="clock-date" id="clock-date"></div>
</div>

<script>
let MAX_ROWS = 500;
let autoScroll = true;
let searchQuery = '';

// ---- 設定ロード ----
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const { raw_hex_visible, max_display_rows } = await res.json();
    setRawHexVisible(raw_hex_visible);
    MAX_ROWS = max_display_rows || 500;
    const sel = document.getElementById('sel-max-rows');
    sel.value = String(MAX_ROWS);
  } catch (e) {}
}

function setRawHexVisible(visible) {
  if (visible) {
    document.body.classList.remove('raw-hex-hidden');
  } else {
    document.body.classList.add('raw-hex-hidden');
  }
  updateRawHexBtn(visible);
}

function updateRawHexBtn(visible) {
  const btn = document.getElementById('btn-raw-hex');
  // "Raw Hex: 表示" / "Raw Hex: 非表示"
  btn.textContent = 'Raw Hex: ' + (visible
    ? _fc(0x8868, 0x793a)
    : _fc(0x975e, 0x8868, 0x793a));
}

async function toggleRawHex() {
  const hidden = document.body.classList.toggle('raw-hex-hidden');
  const visible = !hidden;
  updateRawHexBtn(visible);
  try {
    await fetch('/api/settings/raw_hex_visible', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ visible })
    });
  } catch (e) {}
}

// ---- ポート管理 ----
async function loadPorts() {
  try {
    const res = await fetch('/api/ports');
    const { ports } = await res.json();
    renderPorts(ports);
  } catch (e) {
    console.error('ポート取得エラー', e);
  }
}

function updatePortBadge(connCount, total) {
  const badge = document.getElementById('port-count-badge');
  if (total === 0 || connCount === 0) {
    badge.textContent = _fc(0x63a5, 0x7d9a, 0x306a, 0x3057); // 接続なし
  } else {
    badge.textContent = connCount + ' ' + _fc(0x63a5, 0x7d9a); // N接続
  }
}

function renderPorts(ports) {
  const container = document.getElementById('port-list');
  container.innerHTML = '';
  const connCount = ports.filter(p => p.connected).length;
  updatePortBadge(connCount, ports.length);
  if (ports.length === 0) {
    container.innerHTML =
      '<div style="padding:8px 12px;color:#8090b0;font-size:12px;">利用可能なポートなし</div>';
    return;
  }
  ports.forEach(p => {
    const item = document.createElement('div');
    item.className = 'port-item' + (p.connected ? ' connected' : '');
    item.id = 'port-item-' + encodePortId(p.name);

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = 'cb-' + encodePortId(p.name);
    cb.checked = p.connected;
    cb.addEventListener('change', () => togglePort(p.name, cb.checked, item));

    const lbl = document.createElement('label');
    lbl.htmlFor = cb.id;
    lbl.textContent = p.name;

    item.appendChild(cb);
    item.appendChild(lbl);
    container.appendChild(item);
  });
}

function encodePortId(name) {
  return name.replace(/[^a-zA-Z0-9]/g, '_');
}

function togglePortDropdown() {
  document.getElementById('port-panel').classList.toggle('open');
}

document.addEventListener('click', (e) => {
  if (!document.getElementById('port-dropdown').contains(e.target)) {
    document.getElementById('port-panel').classList.remove('open');
  }
});

async function togglePort(portName, checked, item) {
  const url = checked ? '/api/ports/connect' : '/api/ports/disconnect';
  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port: portName })
    });
    if (checked) {
      item.classList.add('connected');
    } else {
      item.classList.remove('connected');
    }
    const checkedCount = document.querySelectorAll(
      '#port-list input[type=checkbox]:checked'
    ).length;
    const total = document.querySelectorAll(
      '#port-list input[type=checkbox]'
    ).length;
    updatePortBadge(checkedCount, total);
  } catch (e) {
    console.error('ポート切替エラー', e);
  }
}

// ---- 最終受信 MSC 大型表示 ----
function updateLastMsc(row) {
  const cmd = row.command || '';
  let cmdClass = 'lm-command';
  if (cmd === 'GO' || cmd === 'TIMED_GO' || cmd === 'RESUME' || cmd === 'LOAD') {
    cmdClass += ' cmd-go';
  } else if (cmd === 'STOP' || cmd === 'ALL_OFF' || cmd === 'RESET' || cmd === 'GO_OFF') {
    cmdClass += ' cmd-stop';
  } else if (cmd) {
    cmdClass += ' cmd-other';
  }

  document.getElementById('lm-devid').textContent = row.device_id ? 'Id: ' + row.device_id : '';
  document.getElementById('lm-list').textContent  = row.q_list    ? 'List: ' + row.q_list : '';
  const cmdEl = document.getElementById('lm-command');
  cmdEl.textContent = cmd;
  cmdEl.className = cmdClass;
  document.getElementById('lm-qnumber').textContent = row.q_number || '--';
  document.getElementById('lm-format').textContent  = row.cmd_format || '';

  // フラッシュアニメーション
  const panel = document.getElementById('last-msc');
  panel.classList.remove('flash');
  void panel.offsetWidth;
  panel.classList.add('flash');
}

// ---- MTC ビューワー ----
const FPS_LABELS = ['24FPS', '25FPS', '30FPS DF', '30FPS'];
function updateMtc(data) {
  const tc =
    String(data.hours).padStart(2, '0') + ':' +
    String(data.minutes).padStart(2, '0') + ':' +
    String(data.seconds).padStart(2, '0') + '.' +
    String(data.frames).padStart(2, '0');
  const el = document.getElementById('mtc-tc');
  el.textContent = tc;
  el.classList.add('active');
  document.getElementById('mtc-fps').textContent = FPS_LABELS[data.fps_code] || '';
}

// ---- SSE ----
function startSSE() {
  const evtSource = new EventSource('/api/events');
  evtSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.event_type === 'msc') {
      appendRow(data);
      updateLastMsc(data);
    } else if (data.event_type === 'mtc') {
      updateMtc(data);
    }
  };
  evtSource.onerror = () => {
    // 再接続は EventSource が自動で行う
  };
}

function appendRow(row) {
  const tbody = document.getElementById('msg-tbody');
  const emptyMsg = document.getElementById('empty-msg');
  emptyMsg.style.display = 'none';

  const tr = document.createElement('tr');

  // Command に応じてスタイルを決定
  const cmd = row.command || '';
  let cmdClass = 'cmd-other';
  if (cmd === 'GO' || cmd === 'TIMED_GO' || cmd === 'RESUME' || cmd === 'LOAD') {
    cmdClass = 'cmd-go';
  } else if (cmd === 'STOP' || cmd === 'ALL_OFF' || cmd === 'RESET' || cmd === 'GO_OFF') {
    cmdClass = 'cmd-stop';
  }

  tr.innerHTML =
    '<td class="td-ts">' + esc(row.timestamp || '') + '</td>' +
    '<td class="td-port">' + esc(row.port || '') + '</td>' +
    '<td class="td-devid">' + esc(row.device_id || '') + '</td>' +
    '<td>' + esc(row.cmd_format || '') + '</td>' +
    '<td class="' + cmdClass + '">' + esc(row.command || '') + '</td>' +
    '<td class="td-qnum">' + esc(row.q_number || '') + '</td>' +
    '<td>' + esc(row.q_list || '') + '</td>' +
    '<td class="td-raw">' + esc(row.raw_hex || '') + '</td>' +
    '<td></td>';

  tbody.appendChild(tr);

  // 最大行数を超えたら先頭を削除
  if (tbody.rows.length > MAX_ROWS) {
    tbody.deleteRow(0);
  }

  updateCount();

  // 検索中は新規行に判定を適用し、トリム後の件数を更新
  if (searchQuery !== '') {
    const qCell = tr.querySelector('td.td-qnum');
    if (qCell && qCell.textContent.includes(searchQuery)) {
      tr.classList.add('search-match');
    }
    const n = tbody.querySelectorAll('tr.search-match').length;
    document.getElementById('search-count').textContent = n + ' ' + _fc(0x4ef6, 0x4e00, 0x81f4);
  }

  if (autoScroll) {
    const wrap = document.getElementById('table-wrap');
    wrap.scrollTop = wrap.scrollHeight;
  }
}

function esc(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function updateCount() {
  const tbody = document.getElementById('msg-tbody');
  document.getElementById('count-badge').textContent = tbody.rows.length + ' ' + _fc(0x4ef6);
}

// ---- システム時計 ----
const _fc = String.fromCharCode;
const WEEKDAYS = [
  _fc(0x65e5,0x66dc,0x65e5), _fc(0x6708,0x66dc,0x65e5), _fc(0x706b,0x66dc,0x65e5),
  _fc(0x6c34,0x66dc,0x65e5), _fc(0x6728,0x66dc,0x65e5), _fc(0x91d1,0x66dc,0x65e5),
  _fc(0x571f,0x66dc,0x65e5)
];
function updateClock() {
  const now = new Date();
  const hm = String(now.getHours()).padStart(2, '0') + ':' +
    String(now.getMinutes()).padStart(2, '0');
  const sec = String(now.getSeconds()).padStart(2,'0');
  const date = now.getFullYear() + _fc(0x5e74) +
    (now.getMonth() + 1) + _fc(0x6708) +
    now.getDate() + _fc(0x65e5) + ' ' + WEEKDAYS[now.getDay()];
  document.getElementById('clock-hm').textContent = hm;
  document.getElementById('clock-sec').textContent = sec;
  document.getElementById('clock-date').textContent = date;
}

// ---- ツールバー操作 ----
async function changeMaxRows(n) {
  MAX_ROWS = n;
  // サーバーバッファから末尾 n 件を取得して再描画
  try {
    const res = await fetch('/api/logs?limit=' + n);
    const { rows } = await res.json();
    const tbody = document.getElementById('msg-tbody');
    tbody.innerHTML = '';
    rows.forEach(row => appendRow(row));
  } catch (e) {}
  // 設定を保存
  try {
    await fetch('/api/settings/max_display_rows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: n })
    });
  } catch (e) {}
}

// ---- 検索 ----
function onSearchInput(val) {
  searchQuery = val.trim().toLowerCase();
  document.getElementById('btn-search-clear').style.display = searchQuery !== '' ? '' : 'none';
  runSearch();
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  searchQuery = '';
  document.getElementById('btn-search-clear').style.display = 'none';
  runSearch();
}

function runSearch() {
  const tbody = document.getElementById('msg-tbody');
  const countEl = document.getElementById('search-count');
  if (searchQuery === '') {
    for (const tr of tbody.querySelectorAll('tr')) {
      tr.classList.remove('search-match');
    }
    countEl.style.display = 'none';
    return;
  }
  let matchCount = 0;
  for (const tr of tbody.querySelectorAll('tr')) {
    const qCell = tr.querySelector('td.td-qnum');
    const match = qCell != null && qCell.textContent.includes(searchQuery);
    tr.classList.toggle('search-match', match);
    if (match) matchCount++;
  }
  countEl.textContent = matchCount + ' ' + _fc(0x4ef6, 0x4e00, 0x81f4);
  countEl.style.display = '';
}

function toggleAutoScroll() {
  autoScroll = !autoScroll;
  const btn = document.getElementById('btn-autoscroll');
  btn.innerHTML = '自動スクロール: ' + (autoScroll ? 'ON' : 'OFF');
  btn.className = 'btn autoscroll-btn' + (autoScroll ? ' active' : '');
}

async function clearLog() {
  try {
    await fetch('/api/clear', { method: 'POST' });
  } catch (e) { /* ignore */ }
  document.getElementById('msg-tbody').innerHTML = '';
  document.getElementById('empty-msg').style.display = '';
  updateCount();
  // 大型表示もリセット
  document.getElementById('lm-devid').textContent  = '';
  document.getElementById('lm-list').textContent   = '';
  document.getElementById('lm-command').textContent = '';
  document.getElementById('lm-command').className  = 'lm-command';
  document.getElementById('lm-qnumber').textContent = '--';
  document.getElementById('lm-format').textContent  = '';
  document.getElementById('last-msc').classList.remove('flash');
  runSearch();
}

async function exportCsv() {
  const btn = document.getElementById('btn-export');
  const origHtml = btn.innerHTML;
  try {
    const res = await fetch('/api/export', { method: 'POST' });
    const { filename } = await res.json();
    // ✓ + ファイル名を表示（3秒後に元に戻す）
    btn.innerHTML = '&#10003; ' + filename;
    setTimeout(() => { btn.innerHTML = origHtml; }, 3000);
  } catch (e) {
    btn.innerHTML = '&#10007; error';
    setTimeout(() => { btn.innerHTML = origHtml; }, 2000);
  }
}

// ---- 初期化 ----
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  // 設定ロード後にバッファの初期ログを取得（ページリロード時に既存ログを復元）
  try {
    const res = await fetch('/api/logs?limit=' + MAX_ROWS);
    const { rows } = await res.json();
    rows.forEach(row => appendRow(row));
  } catch (e) {}
  loadPorts();
  startSSE();
  updateClock();
  const msToNext = 1000 - new Date().getMilliseconds();
  setTimeout(() => { updateClock(); setInterval(updateClock, 1000); }, msToNext);
});
</script>
</body>
</html>
"""

# HTML_UI 定義後に ASCII 変換を実行
# 非ASCII文字 → &#XXXX; に置換した純粋 ASCII バイト列として保持する
_HTML_UI_BYTES = HTML_UI.encode("ascii", "xmlcharrefreplace")

# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Flask を別スレッドで起動
    t = threading.Thread(target=_start_flask, daemon=True)
    t.start()

    # ポートが確定するまで待つ（make_server はスレッド内でバインドするため）
    if not _port_ready.wait(timeout=10.0):
        raise RuntimeError("Flask サーバーが起動しませんでした")

    _wait_for_server()

    # 前回接続していたポートを自動接続
    available = midi_receiver.get_available_ports()
    for port_name in persistence.load_saved_ports():
        if port_name in available:
            midi_receiver.connect_port(port_name)

    # pywebview ウィンドウ作成
    kwargs = {
        "title": APP_NAME,
        "url": f"http://127.0.0.1:{_PORT}/",
        "width": WINDOW_WIDTH,
        "resizable": True,
        "min_size": (WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
    }
    if WINDOW_HEIGHT is not None:
        kwargs["height"] = WINDOW_HEIGHT
    if WINDOW_X is not None:
        kwargs["x"] = WINDOW_X
    if WINDOW_Y is not None:
        kwargs["y"] = WINDOW_Y

    window = webview.create_window(**kwargs)
    webview.start(lambda: window.maximize() if WINDOW_MAXIMIZE else None)

    # ウィンドウが閉じられたら MIDI ポートを切断して終了
    midi_receiver.disconnect_all()
