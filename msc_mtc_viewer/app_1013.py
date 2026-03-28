"""
MSC_MTC_Viewer macOS 10.13 専用エントリーポイント
WKWebView 互換性のため、MSC ログテーブルの sticky header と Export CSV を差し替える。
"""

import os

import app as base

_TABLE_STYLE_OLD = """  .table-wrap {
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
"""

_TABLE_STYLE_NEW = """  .table-wrap {
    flex: 1;
    overflow: auto;
    padding: 0;
  }
  table {
    width: 100%;
    table-layout: fixed;
    border-collapse: separate;
    border-spacing: 0;
    white-space: nowrap;
    font-size: 12px;
  }
  thead {
    background: var(--bg3);
  }
  thead th {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--bg3);
    padding: 7px 10px;
    text-align: left;
    color: var(--accent);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
    letter-spacing: 0.3px;
    box-shadow: inset 0 -1px 0 var(--border);
  }
  tbody tr {
    background: var(--bg2);
    transition: background 0.1s;
  }
  tbody tr:hover { background: #1e3050; }
  tbody td {
    padding: 5px 10px;
    vertical-align: middle;
    border-bottom: 1px solid #1e2e48;
  }
"""

_EXPORT_JS_OLD = """async function exportCsv() {
  if (!await showConfirm('Export current log as CSV?', 'Export', false, exportDir)) return;
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
"""

_EXPORT_JS_NEW = """async function exportCsv() {
  if (!await showConfirm('Export current log as CSV?', 'Export', false, exportDir)) return;
  const btn = document.getElementById('btn-export');
  const origHtml = btn.innerHTML;
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.export_csv) {
      throw new Error('pywebview api is not ready');
    }
    const result = await window.pywebview.api.export_csv();
    if (!result || result.cancelled) {
      return;
    }
    if (!result.ok) {
      throw new Error(result.error || 'export failed');
    }
    btn.innerHTML = '&#10003; ' + (result.filename || 'saved');
    setTimeout(() => { btn.innerHTML = origHtml; }, 3000);
  } catch (e) {
    btn.innerHTML = '&#10007; error';
    setTimeout(() => { btn.innerHTML = origHtml; }, 2000);
  }
}
"""

_CLOCK_WIDTH_OLD = """    width: min(100%, 980px);"""

_CLOCK_WIDTH_NEW = """    width: 100%;
    max-width: 980px;"""

_CLOCK_NULLISH_OLD = """    clockScaleDefault = clampClockScale(clock_scale_default ?? 1.0);
    clockFontDefault = clock_font_default || 'default';
    clockFontOptions = Array.isArray(clock_font_options) ? clock_font_options : [];
    renderClockFontOptions();
    applyClockScale(clock_scale ?? clockScaleDefault);
    applyClockFont(clock_font || clockFontDefault);"""

_CLOCK_NULLISH_NEW = """    clockScaleDefault = clampClockScale(
      clock_scale_default == null ? 1.0 : clock_scale_default
    );
    clockFontDefault = clock_font_default || 'default';
    clockFontOptions = Array.isArray(clock_font_options) ? clock_font_options : [];
    renderClockFontOptions();
    applyClockScale(clock_scale == null ? clockScaleDefault : clock_scale);
    applyClockFont(clock_font || clockFontDefault);"""

_CLOCK_RESIZE_JS_OLD = """function startClockResize(event) {
  const handle = document.getElementById('clock-resize-top');
  clockResizeState = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startScale: clockScale
  };
  handle.classList.add('active');
  handle.setPointerCapture(event.pointerId);
}

function moveClockResize(event) {
  if (!clockResizeState || event.pointerId !== clockResizeState.pointerId) return;
  const deltaY = clockResizeState.startY - event.clientY;
  applyClockScale(clockResizeState.startScale + (deltaY / 220));
}

async function endClockResize(event) {
  if (!clockResizeState || event.pointerId !== clockResizeState.pointerId) return;
  const handle = document.getElementById('clock-resize-top');
  handle.classList.remove('active');
  if (handle.hasPointerCapture(event.pointerId)) {
    handle.releasePointerCapture(event.pointerId);
  }
  clockResizeState = null;
  await saveClockScale();
}

function initClockControls() {
  const handle = document.getElementById('clock-resize-top');
  handle.addEventListener('pointerdown', startClockResize);
  handle.addEventListener('pointermove', moveClockResize);
  handle.addEventListener('pointerup', endClockResize);
  handle.addEventListener('pointercancel', endClockResize);
}
"""

_CLOCK_RESIZE_JS_NEW = """function startClockResize(event) {
  const handle = document.getElementById('clock-resize-top');
  const clientY = event.touches ? event.touches[0].clientY : event.clientY;
  clockResizeState = {
    startY: clientY,
    startScale: clockScale
  };
  handle.classList.add('active');
  event.preventDefault();
}

function moveClockResize(event) {
  if (!clockResizeState) return;
  const clientY = event.touches ? event.touches[0].clientY : event.clientY;
  const deltaY = clockResizeState.startY - clientY;
  applyClockScale(clockResizeState.startScale + (deltaY / 220));
  if (event.cancelable) {
    event.preventDefault();
  }
}

async function endClockResize() {
  if (!clockResizeState) return;
  const handle = document.getElementById('clock-resize-top');
  handle.classList.remove('active');
  clockResizeState = null;
  await saveClockScale();
}

function initClockControls() {
  const handle = document.getElementById('clock-resize-top');
  handle.addEventListener('mousedown', startClockResize);
  document.addEventListener('mousemove', moveClockResize);
  document.addEventListener('mouseup', endClockResize);
  handle.addEventListener('touchstart', startClockResize, { passive: false });
  document.addEventListener('touchmove', moveClockResize, { passive: false });
  document.addEventListener('touchend', endClockResize);
  document.addEventListener('touchcancel', endClockResize);
}
"""


class ExportApi:
    def __init__(self) -> None:
        self.window = None

    def set_window(self, window) -> None:
        self.window = window

    def export_csv(self) -> dict:
        if self.window is None:
            return {"ok": False, "error": "window not ready"}

        filename = base._get_export_filename()
        export_dir = os.path.expanduser(base.EXPORT_DIR)
        os.makedirs(export_dir, exist_ok=True)

        result = self.window.create_file_dialog(
            base.webview.FileDialog.SAVE,
            directory=export_dir,
            save_filename=filename,
            file_types=("CSV files (*.csv)",),
        )
        if not result:
            return {"ok": False, "cancelled": True}

        filepath = result if isinstance(result, str) else result[0]
        try:
            base._write_csv_export(filepath)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "filename": os.path.basename(filepath)}


def _patch_html_for_macos_1013() -> None:
    html = base.HTML_UI
    if _TABLE_STYLE_NEW not in html:
        if _TABLE_STYLE_OLD not in html:
            raise RuntimeError("10.13 用テーブル CSS の差し替え対象が見つかりませんでした")
        html = html.replace(_TABLE_STYLE_OLD, _TABLE_STYLE_NEW, 1)
    if _EXPORT_JS_NEW not in html:
        if _EXPORT_JS_OLD not in html:
            raise RuntimeError("10.13 用 Export CSV の差し替え対象が見つかりませんでした")
        html = html.replace(_EXPORT_JS_OLD, _EXPORT_JS_NEW, 1)
    if _CLOCK_WIDTH_NEW not in html:
        if _CLOCK_WIDTH_OLD not in html:
            raise RuntimeError("10.13 用時計 CSS の差し替え対象が見つかりませんでした")
        html = html.replace(_CLOCK_WIDTH_OLD, _CLOCK_WIDTH_NEW, 1)
    if _CLOCK_NULLISH_NEW not in html:
        if _CLOCK_NULLISH_OLD not in html:
            raise RuntimeError("10.13 用時計設定 JS の差し替え対象が見つかりませんでした")
        html = html.replace(_CLOCK_NULLISH_OLD, _CLOCK_NULLISH_NEW, 1)
    if _CLOCK_RESIZE_JS_NEW not in html:
        if _CLOCK_RESIZE_JS_OLD not in html:
            raise RuntimeError("10.13 用時計ドラッグ JS の差し替え対象が見つかりませんでした")
        html = html.replace(_CLOCK_RESIZE_JS_OLD, _CLOCK_RESIZE_JS_NEW, 1)
    base.HTML_UI = html
    base._HTML_UI_BYTES = html.encode("ascii", "xmlcharrefreplace")


_patch_html_for_macos_1013()


if __name__ == "__main__":
    base.run_app(js_api=ExportApi())
