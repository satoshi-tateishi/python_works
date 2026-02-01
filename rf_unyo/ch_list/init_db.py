import pandas as pd
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
CSV_PATH = BASE_DIR / "data_source" / "final_data.csv"

def init_db():
    print(f"Loading data from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    # SQLiteに接続
    conn = sqlite3.connect(DB_PATH)
    
    # venuesテーブルとして保存
    print(f"Importing data into {DB_PATH} (table: venues)...")
    df.to_sql("venues", conn, if_exists="replace", index=False)
    
    # TVチャンネル情報のインポート
    CH_CSV_PATH = BASE_DIR / "masters" / "tv_channel_japan.csv"
    if CH_CSV_PATH.exists():
        print(f"Importing {CH_CSV_PATH} into tv_channels...")
        df_ch = pd.read_csv(CH_CSV_PATH)
        df_ch.to_sql("tv_channels", conn, if_exists="replace", index=False)

    # デバイス情報のインポート
    DEV_CSV_PATH = BASE_DIR / "masters" / "Devices.csv"
    if DEV_CSV_PATH.exists():
        print(f"Importing {DEV_CSV_PATH} into devices...")
        df_dev = pd.read_csv(DEV_CSV_PATH)
        df_dev.to_sql("devices", conn, if_exists="replace", index=False)
    
    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
