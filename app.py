from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import face_recognition
import numpy as np
import base64
import json
import cv2
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
        img_rgb   = decode_image(data['image'])
        encodings = face_recognition.face_encodings(img_rgb)

        if not encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        embedding = encodings[0].tolist()
        db        = get_db()
        cursor    = db.cursor()
        cursor.execute("""
            INSERT INTO employees
              (emp_code, name, department, designation, shift, face_embedding)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (data['emp_code'], data['name'], data['department'],
              data['designation'], data['shift'], json.dumps(embedding)))
        db.commit()
        return jsonify({"status":  "success",
                        "message": f"{data['name']} registered!"})
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

        if not live_encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        live_enc = live_encodings[0]
        db       = get_db()
        cursor   = db.cursor()
        cursor.execute("""
            SELECT id, emp_code, name, department,
                   designation, shift, face_embedding
            FROM employees WHERE is_active = 1
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
        dept     = emp[3]; desig    = emp[4]; shift = emp[5]
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
            "SELECT start_time FROM shifts WHERE name=%s", (shift,))
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
              (employee_id, emp_code, name, date, check_in,
               shift, department, designation, status)
            VALUES (%s,%s,%s,%s,NOW(),%s,%s,%s,%s)
        """, (emp_id, emp_code, name, today,
              shift, dept, desig, status))
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
            SELECT emp_code, name, department, designation,
                   shift, check_in, status
            FROM attendance WHERE date = CURDATE()
            ORDER BY check_in DESC
        """)
        rows = cursor.fetchall()
        for r in rows:
            r['check_in'] = str(r['check_in'])
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
            SELECT emp_code, name, department, designation,
                   shift, date, check_in, status
            FROM attendance
            WHERE MONTH(date)=%s AND YEAR(date)=%s
            ORDER BY date DESC, name
        """, (month, year))
        rows = cursor.fetchall()
        for r in rows:
            r['date']     = str(r['date'])
            r['check_in'] = str(r['check_in'])
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
            SELECT id, emp_code, name, department,
                   designation, shift, created_at
            FROM employees WHERE is_active = 1
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