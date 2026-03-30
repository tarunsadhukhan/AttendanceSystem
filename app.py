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
# ROUTE 2c — Lookup Employee by emp_code (for tick/check button)
# ════════════════════════════════════════════════════════════
@app.route('/employee/<emp_code>', methods=['GET'])
def get_employee_by_code(emp_code):
    """Look up employee by emp_code — returns name, photo_html, department, etc."""
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT e.id, e.emp_code, e.name, e.photo_html,
                   d.name AS department, o.name AS designation, s.name AS shift
            FROM employees e
            LEFT JOIN departments d  ON e.department_id  = d.id
            LEFT JOIN occupations o  ON e.designation_id = o.id
            LEFT JOIN shifts s       ON e.shift_id       = s.id
            WHERE e.emp_code = %s AND e.is_active = 1
        """, (emp_code,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row:
            return jsonify({"status": "error",
                            "message": f"Employee code '{emp_code}' not found!"}), 404

        print(f"✅ Employee lookup: {row[2]} ({row[1]}), photo_html={'Yes ('+str(len(row[3]))+' chars)' if row[3] else 'None'}")

        return jsonify({
            "status":      "success",
            "emp_code":    row[1],
            "emp_name":    row[2],
            "photo_html":  row[3],
            "department":  row[4],
            "designation": row[5],
            "shift":       row[6],
            "message":     f"Employee found: {row[2]}"
        })
    except Exception as e:
        print(f"❌ Employee lookup error: {str(e)}")
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
        att_type        = data.get('att_type', 'R')  # R=Regular, O=OT, C=Cash

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
                   s.name AS shift, e.photo_html
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
        dept     = emp[7]; desig    = emp[8]; shift    = emp[9]
        photo_html_val = emp[10] if len(emp) > 10 else None

        # Use IDs from request (form selection) -- fallback to employee defaults
        dept_id  = data.get('department_id')  or emp[3]
        desig_id = data.get('designation_id') or emp[4]
        shift_id = data.get('shift_id')       or emp[5]

        # Use attendance_date from request, fallback to today
        att_date = data.get('attendance_date') or str(date.today())

        # Hours from form
        shift_hours   = data.get('shift_hours',   0)
        working_hours = data.get('working_hours', 0)
        idle_hours    = data.get('idle_hours',    0)

        # Status is "Face" for camera-based attendance
        status = "Face"

        # Save the captured camera photo as HTML img tag
        photo_att_html = f'<img src="data:image/jpeg;base64,{data["image"]}" />'
        print(f"[ATT] dept_id={dept_id} shift_id={shift_id} desig_id={desig_id} att_type={att_type} date={att_date} hrs={shift_hours}/{working_hours}/{idle_hours}")

        cursor.execute("""
            INSERT INTO attendance
              (employee_id, emp_code, date, check_in,
               shift_id, department_id, designation_id, status, att_type, photo_att,
               shift_hours, working_hours, idle_hours)
            VALUES (%s,%s,%s,NOW(),%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (emp_id, emp_code, att_date,
              shift_id, dept_id, desig_id, status, att_type, photo_att_html,
              shift_hours, working_hours, idle_hours))
        db.commit()

        return jsonify({
            "status":           "success",
            "message":          "Attendance marked!",
            "employee":         name,
            "emp_code":         emp_code,
            "emp_name":         name,
            "photo_html":       photo_html_val,
            "department":       dept,
            "designation":      desig,
            "shift":            shift,
            "attendance_status": status,
            "att_type":         att_type,
            "time":             datetime.now().strftime("%H:%M:%S"),
            "confidence":       round((1 - float(distances[best_idx]))*100, 1)
        })
    except Exception as e:
        print(f"❌ Attendance error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 3a — Mark Attendance Manually (no face recognition)
# ════════════════════════════════════════════════════════════
@app.route('/mark-attendance', methods=['POST'])
def mark_attendance_manual():
    """Marks attendance manually using employee code. Status = 'Manual'. No photo saved."""
    try:
        data     = request.json
        emp_code = data.get('emp_code', '').strip()
        att_type = data.get('att_type', 'R')  # R=Regular, O=OT, C=Cash

        if not emp_code:
            return jsonify({"status": "error",
                            "message": "Employee code is required!"}), 400

        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT e.id, e.emp_code, e.name, e.photo_html,
                   e.department_id, e.designation_id, e.shift_id,
                   d.name AS department, o.name AS designation, s.name AS shift
            FROM employees e
            LEFT JOIN departments d  ON e.department_id  = d.id
            LEFT JOIN occupations o  ON e.designation_id = o.id
            LEFT JOIN shifts s       ON e.shift_id       = s.id
            WHERE e.emp_code = %s AND e.is_active = 1
        """, (emp_code,))
        row = cursor.fetchone()

        if not row:
            cursor.close(); db.close()
            return jsonify({"status": "error",
                            "message": f"Employee '{emp_code}' not found or inactive!"}), 404

        emp_id   = row[0]; name = row[2]; photo_html_val = row[3]

        # Use attendance_date from request, fallback to today
        att_date = data.get('attendance_date') or str(date.today())

        # Use IDs from request (form selection) — fallback to employee defaults
        dept_id  = data.get('department_id')  or row[4]
        desig_id = data.get('designation_id') or row[5]
        shift_id = data.get('shift_id')       or row[6]

        # Hours from form
        shift_hours   = data.get('shift_hours',   0)
        working_hours = data.get('working_hours', 0)
        idle_hours    = data.get('idle_hours',    0)

        print(f"[MANUAL-ATT] dept_id={dept_id} shift_id={shift_id} desig_id={desig_id} att_type={att_type} date={att_date} hrs={shift_hours}/{working_hours}/{idle_hours}")

        cursor.execute("""
            INSERT INTO attendance
              (employee_id, emp_code, date, check_in,
               shift_id, department_id, designation_id, status, att_type, photo_att,
               shift_hours, working_hours, idle_hours)
            VALUES (%s,%s,%s,NOW(),%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (emp_id, emp_code, att_date,
              shift_id, dept_id, desig_id, 'Manual', att_type, None,
              shift_hours, working_hours, idle_hours))
        db.commit()

        cursor.close(); db.close()

        return jsonify({
            "status":     "success",
            "emp_code":   emp_code,
            "emp_name":   name,
            "photo_html": photo_html_val,
            "message":    f"Attendance marked for {name} (Manual)"
        })
    except Exception as e:
        print(f"❌ Manual attendance error: {str(e)}")
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
                   d.name AS department, o.name AS designation, s.name AS shift,
                   e.photo_html
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
        photo_html_val = emp[7] if len(emp) > 7 else None
        print(f"✅ Face matched: {emp[2]} ({emp[1]}) distance={best_dist:.3f}, photo_html={'Yes ('+str(len(photo_html_val))+' chars)' if photo_html_val else 'None'}")

        return jsonify({
            "status":     "success",
            "emp_code":   emp[1],
            "emp_name":   emp[2],
            "photo_html": photo_html_val,
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
# ROUTE 12 — Dashboard Stats
# ════════════════════════════════════════════════════════════
@app.route('/dashboard-stats', methods=['GET'])
def dashboard_stats():
    """Returns dashboard statistics for a given date."""
    try:
        stat_date = request.args.get('date', str(date.today()))

        db     = get_db()
        cursor = db.cursor(dictionary=True)

        # Total departments
        cursor.execute("SELECT COUNT(*) AS cnt FROM departments")
        total_departments = cursor.fetchone()['cnt']

        # Total designations (occupations)
        cursor.execute("SELECT COUNT(*) AS cnt FROM occupations")
        total_designations = cursor.fetchone()['cnt']

        # Total shifts
        cursor.execute("SELECT COUNT(*) AS cnt FROM shifts")
        total_shifts = cursor.fetchone()['cnt']

        # Total active employees
        cursor.execute("SELECT COUNT(*) AS cnt FROM employees WHERE is_active = 1")
        total_employees = cursor.fetchone()['cnt']

        # Present on that date (distinct emp_code)
        cursor.execute("""
            SELECT COUNT(DISTINCT emp_code) AS cnt
            FROM attendance WHERE date = %s
        """, (stat_date,))
        total_present = cursor.fetchone()['cnt']

        # Present by Face
        cursor.execute("""
            SELECT COUNT(DISTINCT emp_code) AS cnt
            FROM attendance WHERE date = %s AND status = 'Face'
        """, (stat_date,))
        present_face = cursor.fetchone()['cnt']

        # Present by Manual
        cursor.execute("""
            SELECT COUNT(DISTINCT emp_code) AS cnt
            FROM attendance WHERE date = %s AND status = 'Manual'
        """, (stat_date,))
        present_manual = cursor.fetchone()['cnt']

        # Absent = total active employees - present
        total_absent = max(0, total_employees - total_present)

        cursor.close()
        db.close()

        return jsonify({
            'status':             'success',
            'date':               stat_date,
            'total_departments':  total_departments,
            'total_designations': total_designations,
            'total_shifts':       total_shifts,
            'total_employees':    total_employees,
            'total_present':      total_present,
            'present_face':       present_face,
            'present_manual':     present_manual,
            'total_absent':       total_absent
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 13 — Attendance Report (date-range filter)
# ════════════════════════════════════════════════════════════
@app.route('/attendance-report', methods=['GET'])
def attendance_report():
    """Returns attendance records filtered by date range, department, emp_code."""
    try:
        from_date     = request.args.get('from_date')
        to_date       = request.args.get('to_date')
        department_id = request.args.get('department_id')
        emp_code      = request.args.get('emp_code', '').strip()

        if not from_date or not to_date:
            return jsonify({'status': 'error',
                            'message': 'from_date and to_date are required'}), 400

        db     = get_db()
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT a.id, a.emp_code, e.name AS emp_name,
                   COALESCE(d.name, '') AS department_name,
                   COALESCE(o.name, '') AS designation_name,
                   COALESCE(s.name, '') AS shift_name,
                   a.date AS attendance_date,
                   a.check_in AS attendance_time,
                   a.status, a.att_type,
                   COALESCE(a.shift_hours, 0) AS shift_hours,
                   COALESCE(a.working_hours, 0) AS working_hours,
                   COALESCE(a.idle_hours, 0) AS idle_hours,
                   IF(a.photo_att IS NOT NULL, 1, 0) AS has_photo
            FROM attendance a
            LEFT JOIN employees e   ON a.employee_id    = e.id
            LEFT JOIN departments d ON a.department_id   = d.id
            LEFT JOIN occupations o ON a.designation_id  = o.id
            LEFT JOIN shifts s      ON a.shift_id        = s.id
            WHERE a.date BETWEEN %s AND %s
        """
        params = [from_date, to_date]

        if department_id:
            sql += " AND a.department_id = %s"
            params.append(department_id)

        if emp_code:
            sql += " AND a.emp_code LIKE %s"
            params.append(f"%{emp_code}%")

        sql += " ORDER BY a.date DESC, a.check_in DESC"

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                'id':               row['id'],
                'emp_code':         row['emp_code'],
                'emp_name':         row['emp_name'] or '',
                'department_name':  row['department_name'] or '',
                'designation_name': row['designation_name'] or '',
                'shift_name':       row['shift_name'] or '',
                'attendance_date':  str(row['attendance_date']),
                'attendance_time':  str(row['attendance_time']),
                'status':           row['status'] or '',
                'att_type':         row['att_type'] or 'R',
                'shift_hours':      float(row['shift_hours']),
                'working_hours':    float(row['working_hours']),
                'idle_hours':       float(row['idle_hours']),
                'has_photo':        bool(row['has_photo'])
            })

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'data':   data,
            'total':  len(data)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 13b — Get Attendance Photo (on-demand)
# ════════════════════════════════════════════════════════════
@app.route('/attendance-photo/<int:att_id>', methods=['GET'])
def attendance_photo(att_id):
    """Returns the attendance photo for a single record."""
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT photo_att FROM attendance WHERE id = %s", (att_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row or not row.get('photo_att'):
            return jsonify({'status': 'error', 'message': 'No photo'}), 404

        import re as _re
        match = _re.search(r'base64,([^"]+)', row['photo_att'])
        photo_b64 = match.group(1) if match else None

        return jsonify({'status': 'success', 'photo_att': photo_b64})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 14 — Update Employee
# ════════════════════════════════════════════════════════════
@app.route('/employees/<int:emp_id>', methods=['PUT'])
def update_employee(emp_id):
    try:
        data = request.json
        db     = get_db()
        cursor = db.cursor()

        fields = []
        values = []

        if 'name' in data:
            fields.append("name = %s")
            values.append(data['name'])
        if 'emp_code' in data:
            fields.append("emp_code = %s")
            values.append(data['emp_code'])
        if 'department_id' in data:
            fields.append("department_id = %s")
            values.append(data['department_id'])
        if 'designation_id' in data:
            fields.append("designation_id = %s")
            values.append(data['designation_id'])
        if 'shift_id' in data:
            fields.append("shift_id = %s")
            values.append(data['shift_id'])

        # Handle face image update
        if 'face_image' in data and data['face_image']:
            try:
                img_rgb   = decode_image(data['face_image'])
                encodings = face_recognition.face_encodings(img_rgb)
                if encodings:
                    fields.append("face_embedding = %s")
                    values.append(json.dumps(encodings[0].tolist()))
                    photo_html = f'<img src="data:image/jpeg;base64,{data["face_image"]}" />'
                    fields.append("photo_html = %s")
                    values.append(photo_html)
            except Exception as fe:
                print(f"⚠️ Face update skipped: {fe}")

        if not fields:
            return jsonify({"status": "error",
                            "message": "No fields to update!"}), 400

        values.append(emp_id)
        sql = f"UPDATE employees SET {', '.join(fields)} WHERE id = %s"
        cursor.execute(sql, tuple(values))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Employee not found!"}), 404

        cursor.close()
        db.close()
        return jsonify({"status":  "success",
                        "message": "Employee updated!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Employee code already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ════════════════════════════════════════════════════════════
# ROUTE 15 — Delete Employee
# ════════════════════════════════════════════════════════════
@app.route('/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE employees SET is_active = 0 WHERE id = %s
        """, (emp_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Employee not found!"}), 404

        cursor.close()
        db.close()
        return jsonify({"status":  "success",
                        "message": "Employee deleted!"})
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
    print("[OK] Starting Attendance Server...")
    print("[OK] Open http://localhost:5051 to verify")
    app.run(debug=True, host='0.0.0.0', port=5051)