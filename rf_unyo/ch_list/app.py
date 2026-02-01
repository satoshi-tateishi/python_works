from flask import Flask, render_template, request, session, jsonify, send_file
import sqlite3
from pathlib import Path
import io
import openpyxl

app = Flask(__name__)
app.secret_key = "rf_unyo_secret_key"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
MASTER_XLSX = BASE_DIR / "masters" / "master.xlsx"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    if "keep_list" not in session:
        session["keep_list"] = []
    return render_template("index.html")

@app.route("/adjustment")
def adjustment():
    keep_list = session.get("keep_list", [])
    return render_template("adjustment.html", venues=keep_list)

@app.route("/search")
def search():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    
    conn = get_db_connection()
    # 施設名、住所、都道府県名から部分一致検索
    sql = """
        SELECT * FROM venues 
        WHERE 施設名 LIKE ? OR 住所 LIKE ? OR 都道府県名 LIKE ?
        LIMIT 100
    """
    search_term = f"%{query}%"
    results = conn.execute(sql, (search_term, search_term, search_term)).fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in results])

@app.route("/keep", methods=["POST"])
def keep():
    venue_id = request.json.get("id") # 実際にはユニークなIDが必要だが、現在は施設名+住所などで代用検討
    # 簡易的に、行データ丸ごと保存するか、識別子を保存
    venue_data = request.json.get("data")
    
    keep_list = session.get("keep_list", [])
    # 重複チェック（施設名と住所で簡易的に判定）
    if not any(v["施設名"] == venue_data["施設名"] and v["住所"] == venue_data["住所"] for v in keep_list):
        keep_list.append(venue_data)
        session["keep_list"] = keep_list
        session.modified = True
    
    return jsonify({"status": "success", "count": len(keep_list)})

@app.route("/unkeep", methods=["POST"])
def unkeep():
    venue_data = request.json.get("data")
    keep_list = session.get("keep_list", [])
    keep_list = [v for v in keep_list if not (v["施設名"] == venue_data["施設名"] and v["住所"] == venue_data["住所"])]
    session["keep_list"] = keep_list
    session.modified = True
    return jsonify({"status": "success", "count": len(keep_list)})

@app.route("/get_keep_list")
def get_keep_list():
    return jsonify(session.get("keep_list", []))

@app.route("/export", methods=["POST"])
def export():
    data = request.json.get("data", [])
    if not data:
        return "No data", 400

    print(f"DEBUG: Received data for export: {len(data)} venues")

    try:
        wb = openpyxl.load_workbook(MASTER_XLSX)
        
        # 転記の基本設定
        START_ROW = 36
        ROW_OFFSET = 12
        SHEET_NAMES = ["master_01", "master_02", "master_03"]
        
        for i, item in enumerate(data[:12]):
            # シートの選択 (0-3 -> master_01, 4-7 -> master_02, 8-11 -> master_03)
            sheet_idx = i // 4
            target_sheet_name = SHEET_NAMES[sheet_idx]
            
            if target_sheet_name not in wb.sheetnames:
                print(f"DEBUG: Sheet {target_sheet_name} not found, skipping.")
                continue
                
            ws = wb[target_sheet_name]
            
            # シート内での相対インデックス (0, 1, 2, 3)
            idx_in_sheet = i % 4
            current_base_row = START_ROW + (idx_in_sheet * ROW_OFFSET)
            
            venue = item["venue"]
            channels = item["selected_channels"]
            
            print(f"DEBUG: Writing {venue['施設名']} to {target_sheet_name} row {current_base_row}")
            
            # 郵便番号 (J36系)
            ws.cell(row=current_base_row, column=10, value=venue.get("郵便番号", ""))
            
            # 住所 (R36系)
            ws.cell(row=current_base_row, column=18, value=f"{venue.get('都道府県名', '')}{venue.get('住所', '')}")
            
            # 屋内/屋外 (L38系)
            ws.cell(row=current_base_row + 2, column=12, value=venue.get("屋内外", ""))
            
            # 施設名 (R38系)
            ws.cell(row=current_base_row + 2, column=18, value=venue.get("施設名", ""))
            
            # 適用エリア名称 (O40系)
            ws.cell(row=current_base_row + 4, column=15, value=venue.get("適用エリア", ""))
            
            # 使用TVチャンネル (O42系)
            ch_text = ", ".join([str(c) for c in channels])
            cell = ws.cell(row=current_base_row + 6, column=15)
            cell.value = ch_text
            cell.data_type = 's'

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="運用連絡票.xlsx"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
