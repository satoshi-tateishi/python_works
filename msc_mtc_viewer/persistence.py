"""
設定永続化モジュール
接続履歴・UI 設定を JSON ファイルに保存・ロードする。
保存先: config.json の settings_dir（デフォルト: ~/Documents/MSC_MTC_Viewer）
"""

import json
import os
import tempfile
import threading
from pathlib import Path

_SETTINGS_DIR = Path.home() / "Documents" / "MSC_MTC_Viewer"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"
_settings_lock = threading.Lock()  # read-modify-write 競合防止


def init(settings_dir: str | Path) -> None:
    """設定ディレクトリを変更する。app.py から config.json の値を渡して使う。"""
    global _SETTINGS_DIR, _SETTINGS_FILE
    _SETTINGS_DIR = Path(settings_dir).expanduser()
    _SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


# ---------------------------------------------------------------------------
# 内部ヘルパー（read-then-merge で個別キーが上書きされないようにする）
# ---------------------------------------------------------------------------


def _load_all() -> dict:
    """settings.json 全体を読む。失敗時は空 dict。"""
    try:
        with open(_SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    """settings.json 全体を書く。tempfile + os.replace() でアトミック書き込み。"""
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=_SETTINGS_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, _SETTINGS_FILE)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError:
        pass


# ---------------------------------------------------------------------------
# ポート設定
# ---------------------------------------------------------------------------


def load_saved_ports() -> list[str]:
    """保存済みポート名の一覧を返す。ファイルがなければ空リスト。"""
    ports = _load_all().get("saved_ports", [])
    return [p for p in ports if isinstance(p, str)]


def save_connected_ports(ports: list[str]) -> None:
    """現在接続中のポート名一覧を保存する。"""
    with _settings_lock:
        data = _load_all()
        data["saved_ports"] = ports
        _save_all(data)


# ---------------------------------------------------------------------------
# UI 設定
# ---------------------------------------------------------------------------


def load_raw_hex_visible() -> bool:
    """Raw Hex 列の表示状態を返す。デフォルトは True（表示）。"""
    return bool(_load_all().get("raw_hex_visible", True))


def save_raw_hex_visible(visible: bool) -> None:
    """Raw Hex 列の表示状態を保存する。"""
    with _settings_lock:
        data = _load_all()
        data["raw_hex_visible"] = visible
        _save_all(data)


def load_max_display_rows() -> int:
    """ログテーブルの最大表示件数を返す。デフォルトは 500。"""
    val = _load_all().get("max_display_rows", 500)
    return int(val) if val in (500, 1000, 5000) else 500


def save_max_display_rows(rows: int) -> None:
    """ログテーブルの最大表示件数を保存する。"""
    with _settings_lock:
        data = _load_all()
        data["max_display_rows"] = rows
        _save_all(data)
