#!/usr/bin/env python3
"""
Qoo10 ショップスクレイピングツール
カテゴリページからショップ情報（企業名・企業URL）を抽出し、Google Sheetsに転記
"""

import argparse
import json
import random
import time
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from tqdm import tqdm


# Google Sheets APIのスコープ
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def load_json(file_path: str) -> dict:
    """JSONファイルを読み込む"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_config(config_path: str = "config.json") -> dict:
    """設定ファイルを読み込む"""
    return load_json(config_path)


def load_categories(categories_path: str = "categories.json") -> dict:
    """カテゴリ定義を読み込む"""
    return load_json(categories_path)


def connect_google_sheets(credentials_path: str, spreadsheet_id: str) -> gspread.Spreadsheet:
    """Google Sheetsに接続"""
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


def get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, sheet_name: str) -> gspread.Worksheet:
    """ワークシートを取得または作成"""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        # 既存のデータをクリア
        worksheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=8)

    # ヘッダーを設定
    headers = ['ショップ名', 'ショップURL', '販売者/会社名', '住所', 'メール', '連絡先', 'カテゴリ', '文面タイプ']
    worksheet.update(values=[headers], range_name='A1:H1')
    return worksheet


def get_shop_info(page, shop_id: str, max_retries: int = 3) -> dict:
    """ショップページとショップ情報ページから全情報を取得（リトライ機能付き）"""
    result = {
        'shop_name': 'N/A',
        'company_name': 'N/A',
        'address': 'N/A',
        'email': 'N/A',
        'phone': 'N/A'
    }

    for attempt in range(max_retries):
        try:
            # まずショップページからショップ名を取得
            shop_url = f"https://www.qoo10.jp/shop/{shop_id}"
            page.goto(shop_url, timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            time.sleep(0.5)

            # h1見出しからショップ名を取得
            shop_name = page.evaluate('''() => {
                const h1 = document.querySelector('h1');
                if (h1) {
                    return h1.textContent.trim();
                }
                return null;
            }''')
            if shop_name:
                result['shop_name'] = shop_name

            # ショップ情報ページから詳細情報を取得
            shop_info_url = f"https://www.qoo10.jp/shop-info/{shop_id}?global_yn=N"
            page.goto(shop_info_url, timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            time.sleep(0.5)

            # 全情報を一括取得
            info = page.evaluate('''() => {
                const result = {};
                const dts = document.querySelectorAll('dt');
                for (const dt of dts) {
                    const label = dt.textContent.trim();
                    const dd = dt.nextElementSibling;
                    if (dd && dd.tagName === 'DD') {
                        const value = dd.textContent.trim();
                        if (label.includes('販売者') || label.includes('会社名')) {
                            result.company_name = value;
                        } else if (label.includes('住所')) {
                            result.address = value;
                        } else if (label.includes('メール')) {
                            result.email = value;
                        } else if (label.includes('連絡先')) {
                            result.phone = value;
                        }
                    }
                }
                return result;
            }''')

            if info:
                if info.get('company_name'):
                    result['company_name'] = info['company_name']
                if info.get('address'):
                    result['address'] = info['address']
                if info.get('email'):
                    result['email'] = info['email']
                if info.get('phone'):
                    result['phone'] = info['phone']

            # 成功したらループを抜ける
            break

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    リトライ {attempt + 1}/{max_retries}: {shop_id}")
                time.sleep(2)  # リトライ前に待機
            else:
                print(f"    ショップ情報取得エラー: {shop_id} - {str(e)[:50]}")

    return result


def get_shop_urls_from_category(page, category_url: str, limit: int = 50) -> list[str]:
    """カテゴリページからショップURLを直接取得（無限スクロール対応）"""
    shop_urls = []

    try:
        page.goto(category_url, timeout=60000)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(1)

        # 無限スクロールで商品を読み込む
        max_scrolls = 30  # 最大スクロール回数
        prev_count = 0
        no_change_count = 0

        for i in range(max_scrolls):
            # 現在のショップリンク数を取得
            current_count = page.evaluate('''() => {
                return document.querySelectorAll('a[href*="/shop/"]').length;
            }''')

            # 新しいコンテンツが読み込まれなくなったら終了
            if current_count == prev_count:
                no_change_count += 1
                if no_change_count >= 2:  # 2回連続で変化なしなら終了
                    break
            else:
                no_change_count = 0

            prev_count = current_count
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1.0)  # 読み込み待機

        # ショップリンクを直接取得（JavaScriptで効率的に取得）
        shop_links = page.evaluate('''() => {
            const links = document.querySelectorAll('a[href*="/shop/"]');
            const shops = new Set();
            for (const link of links) {
                const href = link.getAttribute('href');
                if (href && href.includes('/shop/') && !href.includes('shop-info') && !href.includes('shop-qna')) {
                    // shop/xxxの形式からショップIDを抽出（フラグメント#を除外）
                    const match = href.match(/\\/shop\\/([^/?#]+)/);
                    if (match) {
                        shops.add(match[1]);
                    }
                }
            }
            return Array.from(shops);
        }''')

        shop_urls = [f"https://www.qoo10.jp/shop/{shop_id}" for shop_id in shop_links[:limit * 2]]

    except Exception as e:
        print(f"  カテゴリページエラー: {category_url} - {str(e)[:50]}")

    return shop_urls


def scrape_category(page, category_name: str, subcategory: dict, template: str,
                    limit: int, delay: float, existing_shops: set) -> list[dict]:
    """カテゴリをスクレイピング"""
    results = []
    subcategory_name = subcategory['name']
    subcategory_url = subcategory['url']

    print(f"\n  [{subcategory_name}] からショップ取得中...")
    shop_urls = get_shop_urls_from_category(page, subcategory_url, limit * 2)

    print(f"  {len(shop_urls)}件のショップリンクを発見")

    shops_found = 0
    for shop_url in tqdm(shop_urls, desc=f"  {subcategory_name}", leave=False):
        if shops_found >= limit:
            break

        # 既に取得済みのショップはスキップ
        if shop_url in existing_shops:
            continue

        # ショップIDを抽出（フラグメント#やクエリ?を除去）
        shop_id = shop_url.split('/shop/')[-1].split('?')[0].split('#')[0]

        # ショップ情報を取得
        shop_info = get_shop_info(page, shop_id)

        existing_shops.add(shop_url)
        results.append({
            'ショップ名': shop_info['shop_name'],
            'ショップURL': shop_url,
            '販売者/会社名': shop_info['company_name'],
            '住所': shop_info['address'],
            'メール': shop_info['email'],
            '連絡先': shop_info['phone'],
            'カテゴリ': f"{category_name}/{subcategory_name}",
            '文面タイプ': template
        })
        shops_found += 1

        # レート制限対策
        time.sleep(delay + random.uniform(0, 0.5))

    print(f"  → {len(results)}件のショップを取得")
    return results


def main():
    # スクリプトのディレクトリ
    script_dir = Path(__file__).parent
    config_file = script_dir / "config.json"

    # 設定ファイルを読み込み（存在する場合）
    config = {}
    if config_file.exists():
        config = load_config(str(config_file))
        print(f"設定ファイルを読み込みました: {config_file}")

    parser = argparse.ArgumentParser(description='Qoo10ショップスクレイピングツール')
    parser.add_argument('--spreadsheet-id', default=config.get('spreadsheet_id'),
                        help='Google SheetsのスプレッドシートID（config.jsonで設定可）')
    parser.add_argument('--credentials', default=config.get('credentials_path', 'credentials.json'),
                        help='認証ファイルのパス')
    parser.add_argument('--categories', default='categories.json', help='カテゴリ定義ファイルのパス')
    parser.add_argument('--limit', type=int, default=config.get('limit_per_category', 50),
                        help='カテゴリごとの取得上限')
    parser.add_argument('--delay', type=float, default=config.get('request_delay', 1.5),
                        help='リクエスト間隔（秒）')
    parser.add_argument('--category', type=str, default=None,
                        help='特定カテゴリのみ実行（部分一致）')
    args = parser.parse_args()

    # スプレッドシートIDの確認
    if not args.spreadsheet_id or args.spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
        print("エラー: スプレッドシートIDが設定されていません")
        print("config.json の spreadsheet_id を設定するか、--spreadsheet-id オプションを指定してください")
        return 1

    # パスの解決
    credentials_path = script_dir / args.credentials if not Path(args.credentials).is_absolute() else Path(args.credentials)
    categories_path = script_dir / args.categories if not Path(args.categories).is_absolute() else Path(args.categories)

    # 認証ファイルの確認
    if not credentials_path.exists():
        print(f"エラー: 認証ファイルが見つかりません: {credentials_path}")
        print("README.mdのセットアップ手順を参照してください。")
        return 1

    # カテゴリ定義の読み込み
    print("カテゴリ定義を読み込み中...")
    config = load_categories(str(categories_path))

    # Google Sheetsに接続
    print("Google Sheetsに接続中...")
    try:
        spreadsheet = connect_google_sheets(str(credentials_path), args.spreadsheet_id)
        print(f"  接続成功: {spreadsheet.title}")
    except Exception as e:
        print(f"エラー: Google Sheetsへの接続に失敗しました: {str(e)}")
        return 1

    # Playwrightでブラウザを起動
    print("ブラウザを起動中...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # 全カテゴリの重複チェック用
        all_existing_shops = set()

        # カテゴリごとに処理
        for category in config['categories']:
            category_name = category['name']

            # カテゴリフィルタリング
            if args.category and args.category not in category_name:
                print(f"\nスキップ: {category_name}（--category '{args.category}' に一致しない）")
                continue
            template = category['template']
            sheet_name = f"{category_name}【{template}】"

            print(f"\n{'='*60}")
            print(f"カテゴリ: {category_name} ({template})")
            print(f"{'='*60}")

            # ワークシートを準備
            worksheet = get_or_create_worksheet(spreadsheet, sheet_name)

            # このカテゴリの結果
            category_results = []

            # 中カテゴリをスクレイピング
            for subcategory in category['subcategories']:
                results = scrape_category(
                    page, category_name, subcategory, template,
                    args.limit, args.delay, all_existing_shops
                )
                category_results.extend(results)

            # Google Sheetsに書き込み
            if category_results:
                df = pd.DataFrame(category_results)
                data = df.values.tolist()
                worksheet.update(values=data, range_name=f'A2:H{len(data)+1}')
                print(f"\n  → Google Sheetsに{len(category_results)}件を書き込みました")
            else:
                print(f"\n  → このカテゴリでは新規ショップが見つかりませんでした")

        browser.close()

    print(f"\n{'='*60}")
    print("完了!")
    print(f"合計: {len(all_existing_shops)}件のユニークショップを取得")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    exit(main())
