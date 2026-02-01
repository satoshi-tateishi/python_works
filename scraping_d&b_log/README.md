# d&b Event Log Collector

d&b audiotechnik パワーアンプ (D20/D40) の Web UI から Event Log (CSV) を自動取得し、Excel にまとめるスクリプトです。

## セットアップ手順

1. **ライブラリのインストール**
   ターミナルで以下のコマンドを実行してください。
   ```bash
   pip install -r requirements.txt
   ```

2. **Playwright のブラウザインストール**
   ```bash
   playwright install chromium
   ```

## 実行方法

1. VS Code で `main.py` を開きます。
2. 実行（F5キー または 右上の実行ボタン）します。
3. ターミナルで IP 範囲の入力を求められるので、入力します。
   - 例: `192.168.13.10-20,25,30-32`

## 重要な注意点 (TODO)

このスクリプトは、実機の DOM 構造に合わせたセレクタの調整が必要です。`main.py` 内の `TODO` コメントを確認し、以下の箇所を実機で調査して修正してください。

- **モデル名の取得**: `collect_event_log` 内の `result["model"]`
- **Event Log への遷移**: `collect_event_log` 内のクリック操作
- **件数ドロップダウン**: `download_csv` 内の `dropdown_selector`
- **ダウンロードボタン**: `download_csv` 内の `download_button_selector`

## 出力

- 出力先: デスクトップ (`~/Desktop/dnb_eventlog.xlsx`)
- `SUMMARY` シート: 全アンプの取得結果一覧
- `ID_xx_Model` シート: 各アンプのログ詳細
