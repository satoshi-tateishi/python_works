from flask import Flask, render_template, request, session, jsonify, send_file
import sqlite3
from pathlib import Path
import io
import openpyxl
import unicodedata
import shutil
import tempfile
import os
import csv
from datetime import datetime

app = Flask(__name__)
app.secret_key = "rf_unyo_secret_key"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
MASTER_XLSX = BASE_DIR / "masters" / "master.xlsx"

def normalize_text(text):
    if text is None:
        return ""
    # 全角英数字を半角に、大文字を小文字に変換
    return unicodedata.normalize('NFKC', str(text)).lower()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLiteで正規化関数を使えるように登録
    conn.create_function("NORM", 1, normalize_text)
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

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/get_settings")
def get_settings():
    conn = get_db_connection()
    member = conn.execute("SELECT * FROM member_info WHERE id = 1").fetchone()
    user = conn.execute("SELECT * FROM onsite_user WHERE id = 1").fetchone()
    conn.close()
    return jsonify({
        "member": dict(member) if member else {},
        "user": dict(user) if user else {}
    })

@app.route("/save_settings", methods=["POST"])
def save_settings():
    data = request.json
    member = data.get("member", {})
    user = data.get("user", {})
    
    conn = get_db_connection()
    conn.execute("""
        UPDATE member_info SET 
        member_num1 = ?, member_num2 = ?, member_name = ?, 
        department = ?, manager = ?, tel = ?, email = ?
        WHERE id = 1
    """, (member.get("member_num1"), member.get("member_num2"), member.get("member_name"),
          member.get("department"), member.get("manager"), member.get("tel"), member.get("email")))
    
    conn.execute("""
        UPDATE onsite_user SET 
        name = ?, furigana = ?, tel = ?, email = ?
        WHERE id = 1
    """, (user.get("name"), user.get("furigana"), user.get("tel"), user.get("email")))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route("/search")
def search():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    
    conn = get_db_connection()
    # 検索語も同様に正規化
    normalized_query = f"%{normalize_text(query)}%"
    
    # 施設名、住所、都道府県名から部分一致検索 (正規化して比較)
    sql = """
        SELECT * FROM venues 
        WHERE NORM(施設名) LIKE ? 
           OR NORM(住所) LIKE ? 
           OR NORM(都道府県名) LIKE ?
        LIMIT 100
    """
    results = conn.execute(sql, (normalized_query, normalized_query, normalized_query)).fetchall()
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
        conn = get_db_connection()
        member = conn.execute("SELECT * FROM member_info WHERE id = 1").fetchone()
        onsite = conn.execute("SELECT * FROM onsite_user WHERE id = 1").fetchone()
        conn.close()

        # テンプレートを一時ファイルにコピー
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, "temp_export.xlsx")
        shutil.copy2(MASTER_XLSX, temp_path)

        wb = openpyxl.load_workbook(temp_path)
        
        # 転記の基本設定
        START_ROW = 36
        ROW_OFFSET = 12
        SHEET_NAMES = ["master_01", "master_02", "master_03"]
        
        # 会員情報・使用者情報の転記（全シート共通）
        for sn in SHEET_NAMES:
            if sn not in wb.sheetnames: continue
            ws = wb[sn]
            
            # 申請区分 (D4)
            ws.cell(row=4, column=4, value="新規")

            if member:
                ws.cell(row=4, column=13, value=member["member_num1"]) # 会員番号1 (M4)
                ws.cell(row=4, column=16, value=member["member_num2"]) # 会員番号2 (P4)
                ws.cell(row=4, column=23, value=member["member_name"]) # 会員名 (W4)
                ws.cell(row=6, column=13, value=member["department"])  # 部署 (M6)
                ws.cell(row=6, column=23, value=member["manager"])     # 運用担当者 (W6)
                ws.cell(row=8, column=13, value=member["tel"])         # Tel (M8)
                ws.cell(row=8, column=23, value=member["email"])       # E-mail (W8)
            if onsite:
                # 氏名とふりがなを組み合わせる
                name_val = onsite["name"]
                if onsite["furigana"]:
                    name_val += f"（{onsite['furigana']}）"
                ws.cell(row=13, column=15, value=name_val)             # 氏名 (O13)
                ws.cell(row=15, column=12, value=onsite["tel"])        # Tel (L15)
                ws.cell(row=15, column=23, value=onsite["email"])      # E-mail (W15)

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
            
            # 郵便番号 (J36系 -> 第10列)
            ws.cell(row=current_base_row, column=10, value=venue.get("郵便番号", ""))
            
            # 住所 (R36系 -> 第18列)
            ws.cell(row=current_base_row, column=18, value=f"{venue.get('都道府県名', '')}{venue.get('住所', '')}")
            
            # 屋内/屋外 (L38系 -> 第12列)
            ws.cell(row=current_base_row + 2, column=12, value=venue.get("屋内外", ""))
            
            # 施設名 (R38系 -> 第18列)
            ws.cell(row=current_base_row + 2, column=18, value=venue.get("施設名", ""))
            
            # 適用エリア名称 (O40系 -> 第15列)
            ws.cell(row=current_base_row + 4, column=15, value=venue.get("適用エリア", ""))
            
            # 使用TVチャンネル (O42系 -> 第15列)
            ch_text = ", ".join([str(c) for c in channels])
            cell = ws.cell(row=current_base_row + 6, column=15)
            cell.value = ch_text
            cell.data_type = 's'

        # 保存してメモリに読み込む
        wb.save(temp_path)
        output = io.BytesIO()
        with open(temp_path, "rb") as f:
            output.write(f.read())
        output.seek(0)

        # 一時ファイルの削除
        shutil.rmtree(temp_dir)

        date_str = datetime.now().strftime("%Y-%m%d")
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"運用連絡票_{date_str}.xlsx"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e), 500

@app.route("/export_wsm", methods=["POST"])
def export_wsm():
    data = request.json
    venue = data.get("venue")
    selected_channels = data.get("selected_channels", [])
    
    if not venue:
        return "No venue data", 400

    try:
        conn = get_db_connection()
        tv_ch_rows = conn.execute("SELECT * FROM tv_channels ORDER BY TVchannel").fetchall()
        conn.close()
        
        tv_ch_map = {row["TVchannel"]: row for row in tv_ch_rows}
        
        output = io.StringIO()
        writer = csv.writer(output, lineterminator='\n')
        writer.writerow(["name", "type", "frequency", "tolerance", "minfrequency", "maxfrequency", "priority", "squelchlevel"])
        
        for ch in range(13, 54):
            ch_key = f"{ch}CH"
            is_available = venue.get(ch_key) == '○'
            is_selected = ch in selected_channels
            
            row_base = tv_ch_map.get(ch)
            if not row_base:
                continue
            
            min_f = row_base["minfrequency"]
            max_f = row_base["maxfrequency"]
            
            # ガードバンド判定ロジック（シームレス版）
            # 下限側の判定
            if ch > 13:
                prev_available = venue.get(f"{ch-1}CH") == '○'
                if is_available != prev_available:
                    # 境界が「可能」と「不可」の間の時、境界を「可能」チャンネル側に1MHz移動
                    if is_available:
                        min_f += 1000  # 使用可能CHなら内側に狭める
                    else:
                        min_f -= 1000  # 使用不可CHなら外側に広げる
            
            # 上限側の判定
            if ch < 53:
                next_available = venue.get(f"{ch+1}CH") == '○'
                if is_available != next_available:
                    # 境界が「可能」と「不可」の間の時、境界を「可能」チャンネル側に1MHz移動
                    if is_available:
                        max_f -= 1000  # 使用可能CHなら内側に狭める
                    else:
                        max_f += 1000  # 使用不可CHなら外側に広げる
            
            row_type = 2 if is_selected else 3
            priority = 2 if is_selected else 4
            
            writer.writerow([
                f"TV {ch}",
                row_type,
                0,
                0,
                min_f,
                max_f,
                priority,
                5
            ])
            
        writer.writerow(["Blocked", 3, 0, 0, 714000, 798000, 4, 5])
        
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        venue_name = venue.get("施設名", "venue")
        safe_name = "".join([c for c in venue_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        date_str = datetime.now().strftime("%Y-%m%d")
        filename = f"chlist_data_{safe_name}_{date_str}.csv"
        
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
