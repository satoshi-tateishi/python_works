"""
MSC_MTC_Viewer macOS 10.13 専用エントリーポイント
WKWebView 互換性のため、MSC ログテーブルの sticky header 実装だけ差し替える。
"""

import app as base

_EXPORT_BUTTON_OLD = (
    '    <button class="btn" id="btn-export" onclick="exportCsv()">Export CSV</button>'
)
_EXPORT_BUTTON_NEW = (
    '    <button class="btn" id="btn-export" onclick="exportCsv()" style="display:none">'
    "Export CSV</button>"
)

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


def _patch_html_for_macos_1013() -> None:
    html = base.HTML_UI
    if _TABLE_STYLE_NEW in html:
        if _EXPORT_BUTTON_NEW in html:
            return
    if _EXPORT_BUTTON_OLD in html:
        html = html.replace(_EXPORT_BUTTON_OLD, _EXPORT_BUTTON_NEW, 1)
    if _TABLE_STYLE_OLD not in html:
        raise RuntimeError("10.13 用テーブル CSS の差し替え対象が見つかりませんでした")
    html = html.replace(_TABLE_STYLE_OLD, _TABLE_STYLE_NEW, 1)
    base.HTML_UI = html
    base._HTML_UI_BYTES = html.encode("ascii", "xmlcharrefreplace")


_patch_html_for_macos_1013()


if __name__ == "__main__":
    base.run_app()
