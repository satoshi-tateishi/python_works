import pandas as pd
import sqlite3
from pathlib import Path

# --- 開発者用ツール ---
# このスクリプトはデータベースを初期化（リセット）するためのものです。
# 既存のCSVファイル（final_data.csvなど）から強制的にデータを再構築します。
# 
# 通常のデータ更新（新しい施設リストExcelの取り込み等）には、
# 同ディレクトリにある 'update_db.py' を使用してください。
# 'update_db.py' は住所照合からDB更新までを自動で行います。

BASE_DIR = Path(__file__).resolve().parent
# database.db は data_source の一つ上の階層 (ch_list) にある
DB_PATH = BASE_DIR.parent / "database.db"
CSV_PATH = BASE_DIR / "final_data.csv"

def init_db():
    print(f"Loading data from {CSV_PATH}...")
    if not CSV_PATH.exists():
        print(f"Error: {CSV_PATH} not found.")
        return

    df = pd.read_csv(CSV_PATH)
    
    # SQLiteに接続
    conn = sqlite3.connect(DB_PATH)
    
    # venuesテーブルとして保存
    print(f"Importing data into {DB_PATH} (table: venues)...")
    df.to_sql("venues", conn, if_exists="replace", index=False)
    
    # TVチャンネル情報のインポート (data_sourceディレクトリ内)
    CH_CSV_PATH = BASE_DIR / "tv_channel_japan.csv"
    if CH_CSV_PATH.exists():
        print(f"Importing {CH_CSV_PATH} into tv_channels...")
        df_ch = pd.read_csv(CH_CSV_PATH)
        df_ch.to_sql("tv_channels", conn, if_exists="replace", index=False)

    # デバイス情報のインポート (data_sourceディレクトリ内)
    DEV_CSV_PATH = BASE_DIR / "Devices.csv"
    if DEV_CSV_PATH.exists():
        print(f"Importing {DEV_CSV_PATH} into devices...")
        df_dev = pd.read_csv(DEV_CSV_PATH)
        df_dev.to_sql("devices", conn, if_exists="replace", index=False)
    
    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
