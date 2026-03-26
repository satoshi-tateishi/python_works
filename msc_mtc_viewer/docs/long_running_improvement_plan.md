# MSC_MTC_Viewer 長時間運転改善計画

## 概要

本アプリは現状の実装を見る限り、典型的な意味での無制限メモリリークは確認できない。
一方で、長時間連続運転を前提にすると、主なリスクは以下に集中している。

- 高頻度入力時のメッセージ欠落
- ログバッファ先頭削除による CPU 効率低下
- 大量行表示時の WKWebView 描画負荷
- MIDI ポート切断時の復旧性不足

長時間運転向けの改善は、メモリ削減そのものよりも、保持上限の明確化、負荷の平準化、接続復旧性の強化を優先する。

---

## 実装済み（2026-03-26）

以下の改善をすべて実施し、IAC を使ったテストで動作確認済み。

### ✅ サーバ側ログバッファを `deque(maxlen=...)` に変更

- `_log_buffer` を `list` → `collections.deque(maxlen=MAX_LOG_ROWS)` に変更
- `append()` 後の手動 `pop(0)` を削除（`O(n)` → `O(1)` の自動管理）
- `/api/logs` のスライスを `list(_log_buffer)[-limit:]` に修正（deque はスライス非対応のため）

### ✅ MIDI ポート切断検知と自動再接続

`app.py` に `_port_monitor()` スレッドを追加（3 秒間隔）。

- `saved_ports ∩ available ∩ !connected` のポートを自動再接続
- `connected ∩ !available` のポートを `disconnect_port()` でクリーンアップ
- `disconnect_port()` の `close_port()` を try/except で保護（dead port 対応）
- 監視スレッドは Flask 起動後にデーモンスレッドとして起動

**ポート切断時の QF クリーンアップ（追加対応）:**

切断後の再接続で MTC が復旧しない問題を調査し、以下の 3 つの根本原因を特定・修正。

| 原因 | 内容 | 修正 |
|-----|------|------|
| A | `disconnect_port()` がキューをクリアしないため残留 QF が残る。`_qf_last_time` は処理時刻で更新されるため、タイムアウトが発火せず旧フレームと新フレームの nibble が混合する | `drain_port_messages(port_name)` を追加し、切断ポートのキューメッセージを選択的に除去 |
| B | ポート切断時に `_reset_qf_state()` が呼ばれない | `_port_monitor()` の切断処理に `with _mtc_lock: _reset_qf_state()` を追加 |
| C | `get_available_ports()` が毎回 `rtmidi.MidiIn()` を new/del し、3 秒ごとに CoreMIDI churn が発生。200Hz の QF 受信に干渉して choppy になる | `_scanner: rtmidi.MidiIn = rtmidi.MidiIn()` をモジュールレベルで保持し、永続スキャナとして再利用 |

**テスト結果:**
- IAC ポートをオフライン → 3〜6 秒以内に badge が更新
- 送信側を再起動せずにポートをオンラインに戻すと MTC が自動復旧
- MTC 表示がぎこちなくなる症状を調査したところ QLab 側の問題と確認（QLab 再起動で解消）

### ✅ JS 定期ポーリングと SSE 自動再接続

- `setInterval(loadPorts, 10000)` で 10 秒ごとにポートバッジを更新
- `evtSource.onerror` に `evtSource.close(); setTimeout(startSSE, 3000)` を追加し SSE 切断後 3 秒で自動再接続

---

## 未実施項目と判断理由

| 項目 | 判断 | 理由 |
|-----|------|------|
| 受信状態表示（dropped_count UI 表示） | 不要 | MSC は低頻度（公演 1 本で数百件程度）。キュー溢れは実用上発生しない |
| UI 描画最適化（仮想化・バッチ描画） | 不要 | 5000 行 WKWebView で現状問題なし |

---

## 現状評価（実装後）

### 1. 受信キュー

- `_message_queue` は `queue.Queue(maxsize=2000)` の固定長（変更なし）
- 破棄数は `_dropped_count` に加算されるが UI 未表示（MSC 低頻度のため不要と判断）

### 2. サーバ側ログ保持

- `_log_buffer` は `deque(maxlen=MAX_LOG_ROWS)` に変更済み ✅
- `append()` で上限超過時に古い要素が自動破棄される（O(1)）

### 3. フロントエンド表示

- UI の既定表示件数は 500 件を維持
- サーバ保持件数（5000）と UI 表示件数を分離した運用を継続

### 4. MIDI 接続復旧性

- `_port_monitor()` スレッドによる 3 秒間隔の切断検知・自動再接続 ✅
- QF 残留メッセージのクリーンアップ・state リセットも実装済み ✅

---

## 受け入れ基準（達成状況）

| 基準 | 状態 |
|-----|------|
| 数時間以上の連続受信でメモリが単調増加し続けない | ✅ deque で保持上限を保証 |
| UI 表示件数既定値でスクロール・検索が劣化しない | ✅ 500 件維持 |
| ログ保持上限達成時に CPU 劣化が顕著でない | ✅ pop(0) を廃止 |
| 5000 件超過時は古いログから自然に押し出される | ✅ deque が自動管理 |
| MIDI 切断・再接続時に状態が分かり復旧方針が一貫 | ✅ 自動再接続実装済み |
