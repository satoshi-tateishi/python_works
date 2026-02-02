# RF運用連絡票作成・チャンネルリスト検索システム

このプロジェクトは、1.3万件の施設データから運用候補地を選定し、技術的な制約（ガードバンド等）を自動計算した上で、運用連絡票やSennheiser WSMアプリへのインポート用CSVファイルを生成するためのデスクトップアプリケーションです。

## 主な機能

1. **施設検索・並べ替え機能**
   - 施設名、住所、都道府県名による高速検索。
   - 気になる施設を一時保存する「キープリスト」。
   - **ドラッグ＆ドロップ**: キープした施設をマウスで自由に並べ替え可能。
2. **チャンネル調整機能**
   - 施設ごとに使用するTVチャンネルを選択。
   - **ガードバンド (GB) 自動計算**: シームレスな周波数配分を実現。
   - **デバイス適合視覚化**: EM 3732 L/N や SR2050 IEM などの対応CHを直感的に表示。
3. **ファイルエクスポート（macOSネイティブ対応）**
   - **Excel報告書**: 指定テンプレート（`master.xlsx`）に最大12施設分を自動転記。
   - **Sennheiser WSM用CSV**: ガードバンド反映済みの周波数リストを出力。
   - **デスクトップ保存**: 保存ボタンを押すと、macOS標準のダイアログが開き、初期値としてデスクトップが選択されます。

## セットアップと起動方法

### 1. 依存関係のインストール
```bash
pip install -r rf_unyo/requirements.txt
```
※ アプリケーション化のために `pywebview`, `pyinstaller` 等を使用しています。

### 2. データベースの初期化・更新
初回起動時やデータを更新したい場合は、以下の統合更新スクリプトを実行します。
```bash
rf_unyo/.venv/bin/python rf_unyo/ch_list/data_source/update_db.py
```
このスクリプトは、`data_source/` 内の Excel/CSV ファイルを読み込み、SQLite データベースを自動構築します。

### 3. アプリケーションの起動（開発モード）
```bash
rf_unyo/.venv/bin/python rf_unyo/ch_list/app.py
```
専用のウィンドウが立ち上がります。ウィンドウを閉じるとアプリも完全に終了します。

## macOSアプリケーションのビルド方法

スタンドアロンの `.app` ファイルを作成する手順です。

1. **Command Line Tools のインストール** (未導入の場合のみ)
   ```bash
   xcode-select --install
   ```
2. **ビルドスクリプトの実行**
   ```bash
   rf_unyo/.venv/bin/python rf_unyo/ch_list/data_source/build_app.py
   ```
   実行後、`rf_unyo/dist/RF_Unyo_System.app` が作成されます。

## ディレクトリ構成

- `rf_unyo/ch_list/app.py`: メインのアプリケーションロジック（WebView/Flask）
- `rf_unyo/ch_list/data_source/`: データソースおよび管理スクリプト
  - `update_db.py`: 住所照合からDB更新までを行う統合スクリプト
  - `build_app.py`: macOS用ビルドスクリプト
  - `init_db.py`: 開発用DBリセットツール
- `rf_unyo/ch_list/masters/`: Excelテンプレートなど
- `rf_unyo/ch_list/templates/`: HTMLテンプレート
- `rf_unyo/ch_list/Requirements_definition_document.txt`: 詳細要件定義書