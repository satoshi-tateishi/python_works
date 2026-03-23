#!/usr/bin/env python3
"""
MSC Decoder - pywebview ネイティブウィンドウビューア
Usage: python app.py
"""

import json
import os
import signal
import socket
from threading import Thread
import time

from flask import Flask, Response, request
import webview

from decoder import decode_mmon_bytes

PORT = 8765

HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MSC Decoder</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 16px;
    max-width: 480px;
  }
  h1 {
    font-size: 1.4rem;
    font-weight: 600;
    margin-bottom: 20px;
    color: #a0c4ff;
    letter-spacing: 0.05em;
  }
  #dropzone {
    border: 2px dashed #4a6fa5;
    border-radius: 12px;
    padding: 40px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: #16213e;
    margin-bottom: 24px;
    font-size: 1rem;
    color: #7a9cc0;
  }
  #dropzone.drag-over {
    border-color: #a0c4ff;
    background: #1e2d50;
    color: #a0c4ff;
  }
  #filename {
    font-size: 0.85rem;
    color: #7a9cc0;
    margin-bottom: 12px;
    min-height: 1.2em;
  }
  #count {
    font-size: 0.85rem;
    color: #6dbf8b;
    margin-bottom: 16px;
    min-height: 1.2em;
  }
  #error {
    color: #ff8080;
    font-size: 0.9rem;
    margin-bottom: 12px;
    min-height: 1.2em;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th {
    background: #0f3460;
    color: #a0c4ff;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    white-space: nowrap;
    border-bottom: 2px solid #4a6fa5;
  }
  td {
    padding: 9px 14px;
    border-bottom: 1px solid #2a2a4a;
    white-space: nowrap;
  }
  tr:hover td { background: #1e2d50; }
  td.cmd-go    { color: #6dbf8b; font-weight: 600; }
  td.cmd-stop  { color: #ff8080; font-weight: 600; }
  td.cmd-other { color: #f0c040; font-weight: 600; }
  td.cue { font-family: "SF Mono", "Menlo", monospace; color: #ffd580; }
  td.page { color: #b0b0d0; }
  td.ts { font-family: "SF Mono", "Menlo", monospace; color: #c0d8f0; }
</style>
</head>
<body>
<h1>MSC Decoder</h1>
<div id="dropzone">
  .mmon ファイルをここにドロップ
</div>
<div id="filename"></div>
<div id="count"></div>
<div id="error"></div>
<div class="table-wrap">
  <table id="result-table" style="display:none">
    <thead>
      <tr>
        <th>タイムスタンプ</th>
        <th>MSC</th>
        <th>コマンド</th>
        <th>page</th>
        <th>Cue No.</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<script>
const dropzone = document.getElementById('dropzone');
const filenameEl = document.getElementById('filename');
const countEl = document.getElementById('count');
const errorEl = document.getElementById('error');
const table = document.getElementById('result-table');
const tbody = document.getElementById('tbody');

dropzone.addEventListener('dragover', e => {
  e.preventDefault();
  dropzone.classList.add('drag-over');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (!file) return;
  loadFile(file);
});
dropzone.addEventListener('click', () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.mmon';
  input.onchange = e => { if (e.target.files[0]) loadFile(e.target.files[0]); };
  input.click();
});

function loadFile(file) {
  filenameEl.textContent = file.name;
  errorEl.textContent = '';
  countEl.textContent = '解析中...';
  table.style.display = 'none';

  const reader = new FileReader();
  reader.onload = async e => {
    try {
      const resp = await fetch('/decode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: e.target.result
      });
      const data = await resp.json();
      if (data.error) {
        errorEl.textContent = 'エラー: ' + data.error;
        countEl.textContent = '';
        return;
      }
      renderTable(data.rows);
      countEl.textContent = `${data.rows.length} 件のMSCイベント`;
    } catch (err) {
      errorEl.textContent = '通信エラー: ' + err.message;
      countEl.textContent = '';
    }
  };
  reader.readAsArrayBuffer(file);
}

function renderTable(rows) {
  tbody.innerHTML = '';
  for (const row of rows) {
    const tr = document.createElement('tr');
    const cmdClass = row.command === 'GO' ? 'cmd-go'
                   : row.command === 'STOP' ? 'cmd-stop' : 'cmd-other';
    tr.innerHTML = `
      <td class="ts">${esc(row.timestamp)}</td>
      <td>${esc(row.msc)}</td>
      <td class="${cmdClass}">${esc(row.command)}</td>
      <td class="page">${esc(row.page)}</td>
      <td class="cue">${esc(row.cue)}</td>
    `;
    tbody.appendChild(tr);
  }
  table.style.display = rows.length > 0 ? 'table' : 'none';
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body>
</html>
"""

app = Flask(__name__)


@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/decode", methods=["POST"])
def decode():
    try:
        raw = request.get_data()
        rows = decode_mmon_bytes(raw)
        return Response(json.dumps({"rows": rows}, ensure_ascii=False), mimetype="application/json")
    except Exception as e:
        body = json.dumps({"error": str(e)}, ensure_ascii=False)
        return Response(body, mimetype="application/json", status=500)


def _run_flask():
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def _wait_for_server():
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    return False


if __name__ == "__main__":
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()
    if _wait_for_server():
        webview.create_window(
            "MSC Decoder",
            f"http://127.0.0.1:{PORT}",
            width=520,
            height=800,
        )
        webview.start(debug=False)
    os.kill(os.getpid(), signal.SIGTERM)
