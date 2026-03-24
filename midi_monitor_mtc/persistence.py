"""
設定永続化モジュール
接続履歴（最後に使った MIDI ポート名）を JSON ファイルに保存・ロードする。
保存先: ~/.midi_msc_monitor/settings.json
"""

import json
from pathlib import Path

_SETTINGS_DIR = Path.home() / "Documents" / "MIDI MSC Monitor"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


def load_saved_ports() -> list[str]:
    """保存済みポート名の一覧を返す。ファイルがなければ空リスト。"""
    try:
        with open(_SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        ports = data.get("saved_ports", [])
        return [p for p in ports if isinstance(p, str)]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_connected_ports(ports: list[str]) -> None:
    """現在接続中のポート名一覧を保存する。"""
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"saved_ports": ports}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 書き込み失敗はサイレントに無視
