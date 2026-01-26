# Python Works

Pythonで作成したプロジェクト集です。

## Projects

### [scraping](./scraping/)

Qoo10のカテゴリページからショップ情報を抽出し、Google Sheetsに転記するスクレイピングツール。

**主な機能:**
- Playwrightによる無限スクロール対応
- Google Sheets APIとの連携
- リトライ機能・重複排除

**使用技術:** Python, Playwright, Google Sheets API

## Setup

各プロジェクトのディレクトリ内にある `README.md` を参照してください。

共通の依存関係:
```bash
pip install -r <project>/requirements.txt
```

## Author

satoshi-tateishi
