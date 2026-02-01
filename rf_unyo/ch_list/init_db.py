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
    
    # 他の空テーブル（将来用）の作成
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS equipment (id INTEGER PRIMARY KEY, name TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS frequency_map (id INTEGER PRIMARY KEY, frequency REAL, channel INTEGER)")
    
    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
