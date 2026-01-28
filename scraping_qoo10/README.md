# Qoo10 ショップスクレイピングツール

Qoo10のカテゴリページからショップ情報を抽出し、Google Sheetsに転記するPythonスクリプト。

## 機能

- 無限スクロール対応（自動でページ末尾まで商品を読み込み）
- カテゴリ指定オプション（特定カテゴリのみ実行可能）
- リトライ機能（タイムアウト時に最大3回再試行）
- 重複排除（カテゴリ内・カテゴリ間の両方）

## 対象カテゴリ

| 大カテゴリ | 中カテゴリ | 文面タイプ |
|-----------|-----------|-----------|
| ビューティー＆コスメ | スキンケア, ベースメイク, ポイントメイク, ボディ・ハンド・フットケア, 脱毛・除毛, ヘア, メンズビューティー | 文面A |
| サプリ・ダイエット | すべて | 文面A |
| 家電・PC・ゲーム | 美容・健康家電, 電子タバコ・加熱式たばこ | 文面B |
| ペットフード・用品 | 犬用品, 猫用品 | 新文面 |

## セットアップ

### 1. Google Sheets API認証設定

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」から「Google Sheets API」を有効化
3. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」
4. サービスアカウント作成後、「キー」タブで「鍵を追加」→「新しい鍵を作成」→「JSON」
5. ダウンロードしたJSONファイルを `credentials.json` として本ディレクトリに保存

### 2. Google Sheetsの準備

1. [Google Sheets](https://sheets.google.com/) で新しいスプレッドシートを作成
2. スプレッドシートの共有設定で、サービスアカウントのメールアドレス（`credentials.json`内の`client_email`）に「編集者」権限を付与
3. スプレッドシートのURLからスプレッドシートIDを取得
   - URL例: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
   - `SPREADSHEET_ID` の部分がスプレッドシートID

### 3. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
playwright install chromium
```

## 使い方

### 設定ファイル（推奨）

`config.json` を編集してスプレッドシートIDを設定:

```json
{
  "spreadsheet_id": "YOUR_SPREADSHEET_ID_HERE",
  "credentials_path": "credentials.json",
  "limit_per_category": 50,
  "request_delay": 1.5
}
```

### コマンドラインオプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--spreadsheet-id` | Google SheetsのスプレッドシートID | config.jsonの値 |
| `--credentials` | 認証ファイルのパス | `credentials.json` |
| `--categories` | カテゴリ定義ファイルのパス | `categories.json` |
| `--limit` | カテゴリごとの取得上限 | 50 |
| `--delay` | リクエスト間隔（秒） | 1.5 |
| `--category` | 特定カテゴリのみ実行（部分一致） | なし（全カテゴリ） |

### 実行例

```bash
# 全カテゴリを実行
python main.py

# 特定カテゴリのみ実行（部分一致）
python main.py --category ビューティー
python main.py --category ペット
python main.py --category 家電

# 取得上限を変更
python main.py --limit 100

# 特定カテゴリを少数で試す
python main.py --category ペット --limit 5

# リクエスト間隔を長めに設定
python main.py --delay 2.0
```

## 出力形式

Google Sheetsに以下の形式で出力されます：

| 列 | 内容 |
|----|------|
| ショップ名 | ショップページのh1見出し |
| ショップURL | ショップページのURL |
| 販売者/会社名 | ショップ情報ページから取得 |
| 住所 | ショップ情報ページから取得 |
| メール | ショップ情報ページから取得 |
| 連絡先 | ショップ情報ページから取得 |
| カテゴリ | 大カテゴリ/中カテゴリ |
| 文面タイプ | 文面A / 文面B / 新文面 |

### シート構成

- シート1: ビューティー＆コスメ【文面A】
- シート2: サプリ・ダイエット【文面A】
- シート3: 家電・PC・ゲーム【文面B】
- シート4: ペットフード・用品【新文面】

## 注意事項

- 重複データは自動的に排除されます（カテゴリ内・カテゴリ間の両方）
- スクレイピングはサーバーに負荷をかけないよう、適切な間隔を空けて実行されます
- 大量のデータを取得する場合は時間がかかります
- タイムアウト時は自動で最大3回リトライします

## ファイル構成

```
scraping/
├── main.py           # メインスクリプト
├── config.json       # 設定ファイル（スプレッドシートID等）
├── categories.json   # カテゴリ定義
├── credentials.json  # Google API認証情報（要作成）
├── requirements.txt  # 依存ライブラリ
└── README.md         # このファイル
```

## トラブルシューティング

### 認証エラーが発生する場合

- `credentials.json` が正しい場所にあるか確認
- サービスアカウントにスプレッドシートへの編集権限が付与されているか確認

### スクレイピングが途中で止まる場合

- ネットワーク接続を確認
- `--delay` オプションでリクエスト間隔を長くしてみる
- `--category` オプションで特定カテゴリのみ実行してみる

### ブラウザが起動しない場合

```bash
playwright install chromium
```
を再実行

### N/Aが多い場合

- ネットワークが不安定な可能性があります
- `--delay` オプションでリクエスト間隔を長くしてみる
- リトライ機能により自動で再試行されますが、それでも失敗する場合はN/Aとして記録されます
