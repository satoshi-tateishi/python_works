# RF運用連絡票作成・チャンネルリスト検索システム

このプロジェクトは、1.3万件の施設データからワイヤレスマイク等の運用候補地を選定し、技術的な制約（ガードバンド等）を自動計算した上で、運用連絡票やSennheiser WSMアプリへのインポート用CSVファイルを生成するためのローカルWebアプリケーションです。

## 主な機能

1. **施設検索・キープ機能**
   - 施設名、住所、都道府県名による高速検索。
   - 気になる施設を一時保存する「キープリスト」。
2. **チャンネル調整機能**
   - 施設ごとに使用するTVチャンネルを選択。
   - **ガードバンド (GB) 自動計算**: 使用可能チャンネルと使用不可チャンネルの境界において、境界線を「使用可能CH」側に1MHz移動させることで、シームレスな周波数配分を実現。
   - **デバイス適合視覚化**: EM 3732 L/N や SR2050 IEM などのデバイスが、どのチャンネルで運用可能かをカラーラインで直感的に表示。
3. **ファイルエクスポート**
   - **Excel報告書**: 指定のテンプレート（`master.xlsx`）に最大12施設分を自動転記して出力。
   - **Sennheiser WSM用CSV**: WSMアプリにインポート可能な、ガードバンド調整済み周波数リストを施設ごとに出力。

## 技術スタック

- **Backend**: Python 3.12.3 / Flask
- **Database**: SQLite
- **Frontend**: Tailwind CSS
- **Libraries**:
  - `openpyxl`: Excel操作
  - `pandas`: データベース初期化
  - `unicodedata`: 検索語の正規化

## セットアップと起動方法

### 1. 依存関係のインストール
仮想環境（.venv）を有効にした状態で以下を実行します。
```bash
pip install -r rf_unyo/requirements.txt
```
※ アプリケーション化のために `pywebview` を使用しています。

### 5. macOSアプリケーションのビルド方法
本システムをスタンドアロンのmacOSアプリ（.app）としてパッケージングする場合は、以下の手順を実行します。

#### 事前準備: Command Line Tools のインストール
アプリ化ツール（PyInstaller）がバイナリファイルを処理するために、macOS標準の開発者ツールが必要です。
```bash
xcode-select --install
```

#### ビルドの実行
以下のコマンドを実行します。
```bash
rf_unyo/.venv/bin/python rf_unyo/ch_list/data_source/build_app.py
```
実行後、`rf_unyo/dist/RF_Unyo_System.app` が作成されます。

**WebView版の特徴**:
- 起動すると専用のウィンドウが立ち上がります。
- Dockにアイコンが確実に表示されます。
- ウィンドウを閉じると、サーバーを含めアプリケーション全体が完全に終了します。

## ディレクトリ構成

- `rf_unyo/ch_list/app.py`: メインのアプリケーションロジック
- `rf_unyo/ch_list/data_source/`: データソース（CSV/Excel）およびDB更新スクリプト
  - `update_db.py`: DB更新用スクリプト（通常はこちらを使用）
  - `init_db.py`: 開発用DBリセットスクリプト
- `rf_unyo/ch_list/masters/`: Excelテンプレートなど
- `rf_unyo/ch_list/templates/`: HTMLテンプレート
- `rf_unyo/ch_list/Requirements_definition_document.txt`: 詳細要件定義書
