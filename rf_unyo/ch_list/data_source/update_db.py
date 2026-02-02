import pandas as pd
from pathlib import Path
import unicodedata
import re
import sqlite3
import shutil
import os

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent
# database.db は data_source の一つ上の階層 (ch_list) にある
DB_PATH = BASE_DIR.parent / "database.db"

ZIP_CSV = "utf_ken_all.csv"
FACILITY_XLSX = "analoglist-20250831.xlsx"
OUTPUT_XLSX = "analoglist_with_zip.xlsx"

def normalize_address(text):
    if not isinstance(text, str): return ""
    text = unicodedata.normalize('NFKC', text)
    kanji_map = str.maketrans('一二三四五六七八九〇', '1234567890')
    text = text.translate(kanji_map)
    text = re.sub(r'([0-9]+)丁目', r'\1-', text)
    text = re.sub(r'([0-9]+)番[地丁]?', r'\1-', text)
    text = re.sub(r'([0-9]+)号', r'\1', text)
    text = text.replace(' ', '').replace('　', '')
    text = re.sub(r'-+', '-', text).strip('-')
    return text

def backup_database():
    """データベースのバックアップを作成"""
    if DB_PATH.exists():
        backup_path = DB_PATH.with_suffix(".db.bak")
        try:
            shutil.copy2(DB_PATH, backup_path)
            print(f"✅ バックアップ作成完了: {backup_path.name}")
            return True
        except Exception as e:
            print(f"❌ バックアップ作成失敗: {e}")
            return False
    else:
        print(f"⚠️ データベースファイルが見つかりません: {DB_PATH}")
        return False

def update_database(df):
    """DataFrameの内容でvenuesテーブルを更新。他テーブルも同期。"""
    print(f"データベース更新中: {DB_PATH.name}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        # 1. venuesテーブルの更新
        print("  - venuesテーブルを更新中...")
        df.to_sql("venues", conn, if_exists="replace", index=False)
        
        # 2. TVチャンネル情報の同期 (data_sourceにある場合)
        CH_CSV = BASE_DIR / "tv_channel_japan.csv"
        if CH_CSV.exists():
            print("  - tv_channelsテーブルを更新中...")
            pd.read_csv(CH_CSV).to_sql("tv_channels", conn, if_exists="replace", index=False)

        # 3. デバイス情報の同期 (data_sourceにある場合)
        DEV_CSV = BASE_DIR / "Devices.csv"
        if DEV_CSV.exists():
            print("  - devicesテーブルを更新中...")
            pd.read_csv(DEV_CSV).to_sql("devices", conn, if_exists="replace", index=False)
            
        conn.commit()
        conn.close()
        print("✅ データベースの更新が完了しました。")
    except Exception as e:
        print(f"❌ データベース更新エラー: {e}")
        raise e

def main():
    try:
        print("--- 処理開始 ---")
        
        # 0. データベースのバックアップ
        backup_database()

        # 1. 郵便番号CSVの読み込み
        zip_path = BASE_DIR / ZIP_CSV
        if not zip_path.exists():
            raise FileNotFoundError(f"郵便番号CSVが見つかりません: {zip_path}")
            
        print(f"読み込み中: {ZIP_CSV}...")
        zip_df = pd.read_csv(zip_path, header=None, dtype={2: str}, encoding='utf-8')
        zip_df = zip_df[[2, 6, 7, 8]]
        zip_df.columns = ['zip', 'pref', 'city', 'town']
        zip_df['town'] = zip_df['town'].replace('以下に掲載がない場合', '')
        
        print("郵便番号マスター構築中（高速マッチング用）...")
        zip_list = []
        for _, row in zip_df.iterrows():
            full = normalize_address(str(row['pref']) + str(row['city']) + str(row['town']))
            if full:
                zip_list.append((full, row['zip']))
        
        # 2. 施設リスト(Excel)の読み込み
        xlsx_path = BASE_DIR / FACILITY_XLSX
        if not xlsx_path.exists():
            raise FileNotFoundError(f"施設リストExcelが見つかりません: {xlsx_path}")
            
        f_df = pd.read_excel(xlsx_path)

        print(f"住所を照合中（全 {len(f_df)} 件）...")
        zip_list.sort(key=lambda x: len(x[0]), reverse=True)

        def find_zip_code(row):
            raw_addr = str(row['都道府県名']) + str(row['住所'])
            norm_target = normalize_address(raw_addr)
            if not norm_target: return ""
            for addr_key, zip_code in zip_list:
                if addr_key in norm_target:
                    return zip_code
            return ""
        
        f_df['53CH'] = '○'
        f_df['郵便番号'] = f_df.apply(find_zip_code, axis=1)
        f_df['郵便番号'] = f_df['郵便番号'].apply(lambda x: f"{x[:3]}-{x[3:]}" if len(str(x)) == 7 else x)

        cols = f_df.columns.tolist()
        if '郵便番号' in cols:
            cols.insert(0, cols.pop(cols.index('郵便番号')))
            f_df = f_df[cols]

        # 4. Excel保存 (確認用)
        f_df.to_excel(BASE_DIR / OUTPUT_XLSX, index=False)
        print(f"Excelファイル保存完了: {OUTPUT_XLSX}")

        # 5. データベース自動更新
        update_database(f_df)
        
        success_count = (f_df['郵便番号'] != "").sum()
        print(f"\nすべての処理が正常に終了しました！ 照合成功: {success_count} / {len(f_df)} 件")

    except Exception as e:
        print(f"\n❌ 重大なエラーが発生しました: {e}")
        print("データベースが破損した可能性がある場合は、作成されたバックアップ(.db.bak)から復元してください。")

if __name__ == "__main__":
    main()
