import pandas as pd
from pathlib import Path
import unicodedata
import re

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent
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

def main():
    try:
        # 1. 郵便番号CSVの読み込み
        zip_path = BASE_DIR / ZIP_CSV
        print(f"読み込み中: {ZIP_CSV}...")
        zip_df = pd.read_csv(zip_path, header=None, dtype={2: str}, encoding='utf-8')
        zip_df = zip_df[[2, 6, 7, 8]]
        zip_df.columns = ['zip', 'pref', 'city', 'town']
        zip_df['town'] = zip_df['town'].replace('以下に掲載がない場合', '')
        
        print("郵便番号マスター構築中（高速マッチング用）...")
        # 長い住所（詳細な住所）から順に並べることで、より正確なマッチングを狙います
        zip_list = []
        for _, row in zip_df.iterrows():
            full = normalize_address(str(row['pref']) + str(row['city']) + str(row['town']))
            if full:
                zip_list.append((full, row['zip']))
        
        # 2. 施設リスト(Excel)の読み込み
        xlsx_path = BASE_DIR / FACILITY_XLSX
        f_df = pd.read_excel(xlsx_path)

        print(f"住所を照合中（全 {len(f_df)} 件）...")

        # 照合用辞書（さらに高速化）
        # 文字数が多い順にソートしておく（「千代田区麹町3丁目」を「千代田区」より先に判定させるため）
        zip_list.sort(key=lambda x: len(x[0]), reverse=True)

        def find_zip_code(row):
            # A列(都道府県名) と B列(住所) を結合して正規化
            raw_addr = str(row['都道府県名']) + str(row['住所'])
            norm_target = normalize_address(raw_addr)
            
            if not norm_target: return ""

            # 郵便番号リストから、ターゲット住所に含まれているものを探す
            for addr_key, zip_code in zip_list:
                if addr_key in norm_target:
                    return zip_code
            return ""
        
        # --- 53CH（ラジオマイク専用帯）の列を自動追加 ---
        # すべての行に対して「○」を代入
        f_df['53CH'] = '○'
        print("53CH（専用帯）の列を追加しました。")

        # 行全体を渡して処理
        f_df['郵便番号'] = f_df.apply(find_zip_code, axis=1)

        # ここでハイフンを入れる
        f_df['郵便番号'] = f_df['郵便番号'].apply(lambda x: f"{x[:3]}-{x[3:]}" if len(str(x)) == 7 else x)

        # 3. 列移動
        cols = f_df.columns.tolist()
        if '郵便番号' in cols:
            cols.insert(0, cols.pop(cols.index('郵便番号')))
            f_df = f_df[cols]

        # 4. 保存
        f_df.to_excel(BASE_DIR / OUTPUT_XLSX, index=False)
        
        success_count = (f_df['郵便番号'] != "").sum()
        print(f"\n完了！ 照合成功: {success_count} / {len(f_df)} 件")

    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    main()