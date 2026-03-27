from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import face_recognition
import numpy as np
import base64
import json
import cv2
import os
import re
from datetime import datetime, date
from db import get_db, init_db
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)


# ── Decode Base64 image ──────────────────────────────────────
def decode_image(base64_str):
    img_data = base64.b64decode(base64_str)
    np_arr   = np.frombuffer(img_data, np.uint8)
    img_bgr  = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    img_rgb  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return img_rgb

# ════════════════════════════════════════════════════════════
# ROUTE 1 — Health Check
# ════════════════════════════════════════════════════════════
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "success",
                    "message": "✅ Attendance Server Running!"})

# ════════════════════════════════════════════════════════════
# ROUTE 2 — Register Employee
# ════════════════════════════════════════════════════════════
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        print(f"📥 Register POST data: {  {k: (v[:50] + '...') if k == 'image' and isinstance(v, str) and len(v) > 50 else v for k, v in data.items()}  }")

        img_rgb   = decode_image(data['image'])
        encodings = face_recognition.face_encodings(img_rgb)
        print (f"🔍 Detected {len(encodings)} face(s) for {data['name']}")

        if not encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        embedding = encodings[0].tolist()
        db        = get_db()
        cursor    = db.cursor()

        # Accept either IDs or names for department/designation/shift
        dept_id  = data.get('department_id')
        desig_id = data.get('designation_id')
        shift_id = data.get('shift_id')

        # If names sent instead of IDs, look them up
        if not dept_id and data.get('department'):
            cursor.execute("SELECT id FROM departments WHERE name = %s", (data['department'],))
            row = cursor.fetchone()
            dept_id = row[0] if row else None

        if not desig_id and data.get('designation'):
            cursor.execute("SELECT id FROM occupations WHERE name = %s", (data['designation'],))
            row = cursor.fetchone()
            desig_id = row[0] if row else None

        if not shift_id and data.get('shift'):
            cursor.execute("SELECT id FROM shifts WHERE name = %s", (data['shift'],))
            row = cursor.fetchone()
            shift_id = row[0] if row else None

        print(f"Registering {data['name']} with emp_code {data['emp_code']} dept={dept_id} desig={desig_id} shift={shift_id}")

        # Build HTML img tag with embedded base64 (no physical file)
        photo_html = None
        try:
            raw_b64 = data['image']  # already base64 from Android
            photo_html = f'<img src="data:image/jpeg;base64,{raw_b64}" />'
            print(f"📸 Photo stored as HTML ({len(photo_html)} chars)")
        except Exception as pe:
            print(f"⚠️ Photo HTML build failed: {pe}")
            photo_html = None

        cursor.execute("""
            INSERT INTO employees
              (emp_code, name, department_id, designation_id, shift_id, face_embedding, photo_html)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (data['emp_code'], data['name'], dept_id, desig_id, shift_id,
              json.dumps(embedding), photo_html))
        db.commit()
        return jsonify({"status":  "success",
                        "message": f"{data['name']} registered!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Employee code already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 2b — Update Employee Face
# ════════════════════════════════════════════════════════════
@app.route('/register/<emp_code>', methods=['PUT'])
def update_face(emp_code):
    try:
        data = request.json
        img_rgb   = decode_image(data['image'])
        encodings = face_recognition.face_encodings(img_rgb)

        if not encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        embedding = encodings[0].tolist()
        db        = get_db()
        cursor    = db.cursor()
        cursor.execute("""
            UPDATE employees SET face_embedding = %s
            WHERE emp_code = %s
        """, (json.dumps(embedding), emp_code))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Employee not found!"}), 404

        return jsonify({"status":  "success",
                        "message": f"Face updated for emp_code {emp_code}!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 3 — Mark Attendance
# ════════════════════════════════════════════════════════════
@app.route('/attendance', methods=['POST'])
def mark_attendance():
    try:
        data            = request.json
        img_rgb         = decode_image(data['image'])
        live_encodings  = face_recognition.face_encodings(img_rgb)

        print(f"📥 Attendance POST data: {  {k: (v[:50] + '...') if k == 'image' and isinstance(v, str) and len(v) > 50 else v for k, v in data.items()}  }")
        if not live_encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        live_enc = live_encodings[0]
        db       = get_db()
        cursor   = db.cursor()
        cursor.execute("""
            SELECT e.id, e.emp_code, e.name,
                   e.department_id, e.designation_id, e.shift_id,
                   e.face_embedding,
                   d.name AS department, o.name AS designation,
                   s.name AS shift
            FROM employees e
            LEFT JOIN departments d  ON e.department_id  = d.id
            LEFT JOIN occupations o  ON e.designation_id = o.id
            LEFT JOIN shifts s       ON e.shift_id       = s.id
            WHERE e.is_active = 1 AND e.face_embedding IS NOT NULL
        """)
        employees = cursor.fetchall()

        if not employees:
            return jsonify({"status": "error",
                            "message": "No employees registered!"}), 404

        stored_encs = [np.array(json.loads(e[6])) for e in employees]
        matches     = face_recognition.compare_faces(
                          stored_encs, live_enc, tolerance=0.5)
        distances   = face_recognition.face_distance(stored_encs, live_enc)
        best_idx    = int(np.argmin(distances))

        if not matches[best_idx]:
            return jsonify({"status":  "not_recognized",
                            "message": "Face not recognized!"}), 401

        emp      = employees[best_idx]
        emp_id   = emp[0]; emp_code = emp[1]; name = emp[2]
        dept_id  = emp[3]; desig_id = emp[4]; shift_id = emp[5]
        dept     = emp[7]; desig    = emp[8]; shift    = emp[9]
        today    = date.today()

        # Duplicate check
        cursor.execute("""
            SELECT id FROM attendance
            WHERE employee_id=%s AND date=%s
        """, (emp_id, today))
        if cursor.fetchone():
            return jsonify({"status":  "already_marked",
                            "message": f"Already marked for {name} today!"})

        # Late check
        cursor.execute(
            "SELECT start_time FROM shifts WHERE id=%s", (shift_id,))
        row    = cursor.fetchone()
        status = "Present"
        if row:
            now_secs   = (datetime.now().hour * 3600 +
                          datetime.now().minute * 60 +
                          datetime.now().second)
            shift_secs = int(row[0].total_seconds()) + 900  # +15 min
            if now_secs > shift_secs:
                status = "Late"

        cursor.execute("""
            INSERT INTO attendance
              (employee_id, emp_code, date, check_in,
               shift_id, department_id, designation_id, status)
            VALUES (%s,%s,%s,NOW(),%s,%s,%s,%s)
        """, (emp_id, emp_code, today,
              shift_id, dept_id, desig_id, status))
        db.commit()

        return jsonify({
            "status":           "success",
            "message":          "Attendance marked!",
            "employee":         name,
            "emp_code":         emp_code,
            "department":       dept,
            "designation":      desig,
            "shift":            shift,
            "attendance_status": status,
            "time":             datetime.now().strftime("%H:%M:%S"),
            "confidence":       round((1 - float(distances[best_idx]))*100, 1)
        })
    except Exception as e:
        print(f"❌ Attendance error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 3b — Check Face Only (no attendance marking)
# ════════════════════════════════════════════════════════════
@app.route('/check-face', methods=['POST'])
def check_face():
    """Only checks if face exists in DB, returns emp_code & name. Does NOT mark attendance."""
    try:
        data    = request.json
        print(f"📥 Check-face POST: image={len(data.get('image',''))} chars")

        img_rgb = decode_image(data['image'])
        live_encodings = face_recognition.face_encodings(img_rgb)

        if not live_encodings:
            return jsonify({"status": "error",
                            "message": "No face detected in image!"}), 400

        live_enc = live_encodings[0]
        db       = get_db()
        cursor   = db.cursor()
        cursor.execute("""
            SELECT e.id, e.emp_code, e.name, e.face_embedding,
                   d.name AS department, o.name AS designation, s.name AS shift
            FROM employees e
            LEFT JOIN departments d  ON e.department_id  = d.id
            LEFT JOIN occupations o  ON e.designation_id = o.id
            LEFT JOIN shifts s       ON e.shift_id       = s.id
            WHERE e.is_active = 1 AND e.face_embedding IS NOT NULL
        """)
        employees = cursor.fetchall()
        cursor.close()
        db.close()

        if not employees:
            return jsonify({"status": "error",
                            "message": "No employees with face registered!"}), 404

        stored_encs = [np.array(json.loads(e[3])) for e in employees]
        distances   = face_recognition.face_distance(stored_encs, live_enc)
        best_idx    = int(np.argmin(distances))
        best_dist   = float(distances[best_idx])

        if best_dist > 0.5:
            return jsonify({"status":  "not_recognized",
                            "message": "Face not recognized!"}), 401

        emp = employees[best_idx]
        print(f"✅ Face matched: {emp[2]} ({emp[1]}) distance={best_dist:.3f}")

        return jsonify({
            "status":     "success",
            "emp_code":   emp[1],
            "emp_name":   emp[2],
            "department": emp[4],
            "designation":emp[5],
            "shift":      emp[6],
            "confidence": round((1 - best_dist) * 100, 1),
            "message":    f"Face matched: {emp[2]}"
        })
    except Exception as e:
        print(f"❌ Check-face error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 4 — Today's Report
# ════════════════════════════════════════════════════════════
@app.route('/report/today', methods=['GET'])
def today_report():
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.emp_code, e.name, d.name AS department,
                   o.name AS designation, s.name AS shift,
                   a.check_in, a.check_out, a.status
            FROM attendance a
            LEFT JOIN employees e    ON a.employee_id    = e.id
            LEFT JOIN departments d  ON a.department_id  = d.id
            LEFT JOIN occupations o  ON a.designation_id = o.id
            LEFT JOIN shifts s       ON a.shift_id       = s.id
            WHERE a.date = CURDATE()
            ORDER BY a.check_in DESC
        """)
        rows = cursor.fetchall()
        for r in rows:
            r['check_in']  = str(r['check_in'])
            r['check_out'] = str(r['check_out']) if r.get('check_out') else None
        return jsonify({"status": "success",
                        "date":   str(date.today()),
                        "total":  len(rows),
                        "data":   rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 5 — Monthly Report
# ════════════════════════════════════════════════════════════
@app.route('/report/monthly', methods=['GET'])
def monthly_report():
    try:
        month  = request.args.get('month', datetime.now().month)
        year   = request.args.get('year',  datetime.now().year)
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.emp_code, e.name, d.name AS department,
                   o.name AS designation, s.name AS shift,
                   a.date, a.check_in, a.check_out, a.status
            FROM attendance a
            LEFT JOIN employees e    ON a.employee_id    = e.id
            LEFT JOIN departments d  ON a.department_id  = d.id
            LEFT JOIN occupations o  ON a.designation_id = o.id
            LEFT JOIN shifts s       ON a.shift_id       = s.id
            WHERE MONTH(a.date)=%s AND YEAR(a.date)=%s
            ORDER BY a.date DESC, e.name
        """, (month, year))
        rows = cursor.fetchall()
        for r in rows:
            r['date']      = str(r['date'])
            r['check_in']  = str(r['check_in'])
            r['check_out'] = str(r['check_out']) if r.get('check_out') else None
        return jsonify({"status": "success",
                        "month":  month, "year": year,
                        "total":  len(rows), "data": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 6 — All Employees
# ════════════════════════════════════════════════════════════
@app.route('/employees', methods=['GET'])
def get_employees():
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.id, e.emp_code, e.name,
                   e.department_id, e.designation_id, e.shift_id,
                   e.photo_html, e.is_active, e.created_at,
                   d.name AS department_name,
                   o.name AS designation_name,
                   s.name AS shift_name
            FROM employees e
            LEFT JOIN departments d  ON e.department_id  = d.id
            LEFT JOIN occupations o  ON e.designation_id = o.id
            LEFT JOIN shifts s       ON e.shift_id       = s.id
            WHERE e.is_active = 1
            ORDER BY e.name
        """)
        rows = cursor.fetchall()
        for r in rows:
            r['created_at'] = str(r['created_at'])
            # Extract base64 from photo_html field (no physical file)
            r['photo_base64'] = None
            if r.get('photo_html'):
                match = re.search(r'base64,([^"]+)', r['photo_html'])
                if match:
                    r['photo_base64'] = match.group(1)
            # Remove photo_html from response (not needed by client)
            r.pop('photo_html', None)
        return jsonify({"status": "success",
                        "total":  len(rows),
                        "data":   rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 7 — Display All Departments
# ════════════════════════════════════════════════════════════
@app.route('/departments', methods=['GET'])
def get_departments():
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM departments
            ORDER BY name
        """)
        rows = cursor.fetchall()
        return jsonify({"status": "success",
                        "total":  len(rows),
                        "data":   rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 7b — Add Department
# ════════════════════════════════════════════════════════════
@app.route('/departments', methods=['POST'])
def add_department():
    try:
        data = request.json
        name = data.get('name', '').strip()

        if not name:
            return jsonify({"status": "error",
                            "message": "Department name is required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO departments (name) VALUES (%s)
        """, (name,))
        db.commit()
        return jsonify({"status":  "success",
                        "message": f"Department '{name}' added!",
                        "id":      cursor.lastrowid})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Department already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 7c — Edit Department
# ════════════════════════════════════════════════════════════
@app.route('/departments/<int:dept_id>', methods=['PUT'])
def edit_department(dept_id):
    try:
        data = request.json
        name = data.get('name', '').strip()

        if not name:
            return jsonify({"status": "error",
                            "message": "Department name is required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE departments SET name = %s WHERE id = %s
        """, (name, dept_id))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Department not found!"}), 404

        return jsonify({"status":  "success",
                        "message": f"Department updated to '{name}'!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Department name already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 7d — Delete Department
# ════════════════════════════════════════════════════════════
@app.route('/departments/<int:dept_id>', methods=['DELETE'])
def delete_department(dept_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM departments WHERE id = %s", (dept_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Department not found!"}), 404

        return jsonify({"status":  "success",
                        "message": "Department deleted!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 8 — All Shifts
# ════════════════════════════════════════════════════════════
@app.route('/shifts', methods=['GET'])
def get_shifts():
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, name, start_time, end_time
            FROM shifts
            ORDER BY start_time
        """)
        rows = cursor.fetchall()
        for r in rows:
            r['start_time'] = str(r['start_time'])
            r['end_time']   = str(r['end_time'])
        return jsonify({"status": "success",
                        "total":  len(rows),
                        "data":   rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 8b — Add Shift
# ════════════════════════════════════════════════════════════
@app.route('/shifts', methods=['POST'])
def add_shift():
    try:
        data       = request.json
        name       = data.get('name', '').strip()
        start_time = data.get('start_time', '').strip()
        end_time   = data.get('end_time', '').strip()

        if not name or not start_time or not end_time:
            return jsonify({"status": "error",
                            "message": "name, start_time, and end_time are required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO shifts (name, start_time, end_time)
            VALUES (%s, %s, %s)
        """, (name, start_time, end_time))
        db.commit()
        return jsonify({"status":  "success",
                        "message": f"Shift '{name}' added!",
                        "id":      cursor.lastrowid})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Shift already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 8c — Edit Shift
# ════════════════════════════════════════════════════════════
@app.route('/shifts/<int:shift_id>', methods=['PUT'])
def edit_shift(shift_id):
    try:
        data       = request.json
        name       = data.get('name', '').strip()
        start_time = data.get('start_time', '').strip()
        end_time   = data.get('end_time', '').strip()

        if not name or not start_time or not end_time:
            return jsonify({"status": "error",
                            "message": "name, start_time, and end_time are required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE shifts SET name = %s, start_time = %s, end_time = %s
            WHERE id = %s
        """, (name, start_time, end_time, shift_id))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Shift not found!"}), 404

        return jsonify({"status":  "success",
                        "message": f"Shift updated to '{name}'!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Shift name already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 8d — Delete Shift
# ════════════════════════════════════════════════════════════
@app.route('/shifts/<int:shift_id>', methods=['DELETE'])
def delete_shift(shift_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM shifts WHERE id = %s", (shift_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Shift not found!"}), 404

        return jsonify({"status":  "success",
                        "message": "Shift deleted!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 9 — All Occupations
# ════════════════════════════════════════════════════════════
@app.route('/occupations', methods=['GET'])
def get_occupations():
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, name, created_at
            FROM occupations
            ORDER BY name
        """)
        rows = cursor.fetchall()
        for r in rows:
            r['created_at'] = str(r['created_at'])
        return jsonify({"status": "success",
                        "total":  len(rows),
                        "data":   rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 9b — Add Occupation
# ════════════════════════════════════════════════════════════
@app.route('/occupations', methods=['POST'])
def add_occupation():
    try:
        data = request.json
        name = data.get('name', '').strip()

        if not name:
            return jsonify({"status": "error",
                            "message": "Occupation name is required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO occupations (name) VALUES (%s)
        """, (name,))
        db.commit()
        return jsonify({"status":  "success",
                        "message": f"Occupation '{name}' added!",
                        "id":      cursor.lastrowid})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Occupation already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 9c — Edit Occupation
# ════════════════════════════════════════════════════════════
@app.route('/occupations/<int:occ_id>', methods=['PUT'])
def edit_occupation(occ_id):
    try:
        data = request.json
        name = data.get('name', '').strip()

        if not name:
            return jsonify({"status": "error",
                            "message": "Occupation name is required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE occupations SET name = %s WHERE id = %s
        """, (name, occ_id))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Occupation not found!"}), 404

        return jsonify({"status":  "success",
                        "message": f"Occupation updated to '{name}'!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Occupation name already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 9d — Delete Occupation
# ════════════════════════════════════════════════════════════
@app.route('/occupations/<int:occ_id>', methods=['DELETE'])
def delete_occupation(occ_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM occupations WHERE id = %s", (occ_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Occupation not found!"}), 404

        return jsonify({"status":  "success",
                        "message": "Occupation deleted!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 10 — Signup
# ════════════════════════════════════════════════════════════
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        username  = data.get('username', '').strip()
        password  = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        email     = data.get('email', '').strip()
        role      = data.get('role', 'user')

        if not username or not password or not full_name:
            return jsonify({"status": "error",
                            "message": "username, password, and full_name are required!"}), 400

        hashed_pw = generate_password_hash(password)
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, full_name, email, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, hashed_pw, full_name, email, role))
        db.commit()
        return jsonify({"status":  "success",
                        "message": f"User '{username}' created!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Username or email already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 11 — Login
# ════════════════════════════════════════════════════════════
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({"status": "error",
                            "message": "username and password are required!"}), 400

        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, password, full_name, email, role
            FROM users
            WHERE username = %s AND is_active = 1
        """, (username,))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            return jsonify({"status": "error",
                            "message": "Invalid username or password!"}), 401

        return jsonify({
            "status":    "success",
            "message":   "Login successful!",
            "user": {
                "id":        user['id'],
                "username":  user['username'],
                "full_name": user['full_name'],
                "email":     user['email'],
                "role":      user['role']
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# Initialize DB tables on import (for gunicorn)
try:
    init_db()
except Exception as e:
    print(f"⚠️ init_db failed (will retry on first request): {e}")

# ════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("✅ Starting Attendance Server...")
    print("✅ Open http://localhost:5051 to verify")
    app.run(debug=True, host='0.0.0.0', port=5051)