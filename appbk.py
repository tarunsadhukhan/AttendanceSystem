"""
MyHrms - Complete Flask API Server
Run: python app.py
Server will start on http://0.0.0.0:5051

Required packages:
    pip install flask mysql-connector-python face_recognition numpy

Database migration (run these SQL statements if upgrading):
    -- Add photo_html column (replaces photo_path)
    ALTER TABLE employees ADD COLUMN photo_html LONGTEXT DEFAULT NULL;
    ALTER TABLE employees DROP COLUMN photo_path;

    -- Create attendance table (multiple entries allowed)
    CREATE TABLE IF NOT EXISTS attendance (
        id INT NOT NULL AUTO_INCREMENT,
        emp_id INT NOT NULL,
        emp_code VARCHAR(20) NOT NULL,
        attendance_date DATE NOT NULL,
        attendance_time TIME NOT NULL,
        status VARCHAR(10) DEFAULT 'Manual',
        att_type CHAR(1) DEFAULT 'R',
        photo_att LONGTEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_emp_date (emp_code, attendance_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

    -- If upgrading, add columns:
    ALTER TABLE attendance ADD COLUMN status VARCHAR(10) DEFAULT 'Manual';
    ALTER TABLE attendance ADD COLUMN att_type CHAR(1) DEFAULT 'R';
    ALTER TABLE attendance ADD COLUMN photo_att LONGTEXT DEFAULT NULL;
"""

import os
import base64
import json
import numpy as np
from flask import Flask, request, jsonify
from datetime import datetime

# ── Face Recognition (optional) ──────────────────────────────────
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
    print("✅ face_recognition loaded")
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("⚠️  face_recognition not installed. Face embedding will be skipped.")
    print("   Install with: pip install face_recognition")

app = Flask(__name__)

# Directory to store employee photos
PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employee_photos')
os.makedirs(PHOTO_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════
# DATABASE CONNECTION - UPDATE THESE VALUES
# ══════════════════════════════════════════════════════════════════
DB_CONFIG = {
    'host': '13.126.47.172',
    'user': 'myroot',
    'password': 'deb#9876',
    'database': 'sjm'
}


def get_db():
    import mysql.connector
    return mysql.connector.connect(**DB_CONFIG)


# ══════════════════════════════════════════════════════════════════
# AUTO-MIGRATION — runs once on startup
# ══════════════════════════════════════════════════════════════════

def init_db():
    """Auto-migrate: add photo_html column, convert old photo_path data,
       create attendance table if missing."""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # 1) Check if photo_html column exists
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'employees'
              AND COLUMN_NAME = 'photo_html'
        """, (DB_CONFIG['database'],))
        has_photo_html = cursor.fetchone() is not None

        if not has_photo_html:
            print("🔧 Adding photo_html column to employees table...")
            cursor.execute("ALTER TABLE employees ADD COLUMN photo_html LONGTEXT DEFAULT NULL")
            db.commit()
            print("   ✅ photo_html column added")

        # 2) Check if photo_path column still exists (old schema)
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'employees'
              AND COLUMN_NAME = 'photo_path'
        """, (DB_CONFIG['database'],))
        has_photo_path = cursor.fetchone() is not None

        # 3) Convert old photo_path files → photo_html
        if has_photo_path:
            cursor.execute("""
                SELECT id, photo_path FROM employees
                WHERE photo_path IS NOT NULL AND photo_path != ''
                  AND (photo_html IS NULL OR photo_html = '')
            """)
            rows = cursor.fetchall()
            converted = 0
            for row in rows:
                path = row['photo_path']
                if path and os.path.exists(path):
                    try:
                        with open(path, 'rb') as f:
                            img_b64 = base64.b64encode(f.read()).decode('utf-8')
                        html = f'<img src="data:image/jpeg;base64,{img_b64}" />'
                        cursor.execute(
                            "UPDATE employees SET photo_html = %s WHERE id = %s",
                            (html, row['id'])
                        )
                        converted += 1
                    except Exception as e:
                        print(f"   ⚠️  Could not convert photo for id={row['id']}: {e}")
            if converted:
                db.commit()
                print(f"   ✅ Converted {converted} old photo_path files → photo_html")

        # 4) Create attendance table if missing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INT NOT NULL AUTO_INCREMENT,
                emp_id INT NOT NULL,
                emp_code VARCHAR(20) NOT NULL,
                attendance_date DATE NOT NULL,
                attendance_time TIME NOT NULL,
                status VARCHAR(10) DEFAULT 'Manual',
                att_type CHAR(1) DEFAULT 'R',
                photo_att LONGTEXT DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_emp_date (emp_code, attendance_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        db.commit()

        # 5) Add status column if missing (for existing databases)
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN status VARCHAR(10) DEFAULT 'Manual'
            """)
            db.commit()
            print("   ✅ Added 'status' column to attendance table")
        except Exception:
            pass  # column already exists

        # 6) Add att_type column if missing (R=Regular, O=OT, C=Cash)
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN att_type CHAR(1) DEFAULT 'R'
            """)
            db.commit()
            print("   ✅ Added 'att_type' column to attendance table")
        except Exception:
            pass  # column already exists

        # 7) Add photo_att column if missing (stores attendance photo as HTML img)
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN photo_att LONGTEXT DEFAULT NULL
            """)
            db.commit()
            print("   ✅ Added 'photo_att' column to attendance table")
        except Exception:
            pass  # column already exists

        # 8) Add shift_hours column if missing
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN shift_hours DECIMAL(5,2) DEFAULT 0
            """)
            db.commit()
            print("   ✅ Added 'shift_hours' column to attendance table")
        except Exception:
            pass  # column already exists

        # 9) Add working_hours column if missing
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN working_hours DECIMAL(5,2) DEFAULT 0
            """)
            db.commit()
            print("   ✅ Added 'working_hours' column to attendance table")
        except Exception:
            pass  # column already exists

        # 10) Add idle_hours column if missing
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN idle_hours DECIMAL(5,2) DEFAULT 0
            """)
            db.commit()
            print("   ✅ Added 'idle_hours' column to attendance table")
        except Exception:
            pass  # column already exists

        # 11) Add department_id column if missing
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN department_id INT DEFAULT NULL
            """)
            db.commit()
            print("   ✅ Added 'department_id' column to attendance table")
        except Exception:
            pass  # column already exists

        # 12) Add shift_id column if missing
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN shift_id INT DEFAULT NULL
            """)
            db.commit()
            print("   ✅ Added 'shift_id' column to attendance table")
        except Exception:
            pass  # column already exists

        # 13) Add designation_id column if missing
        try:
            cursor.execute("""
                ALTER TABLE attendance ADD COLUMN designation_id INT DEFAULT NULL
            """)
            db.commit()
            print("   ✅ Added 'designation_id' column to attendance table")
        except Exception:
            pass  # column already exists

        cursor.close()
        db.close()
        print("✅ Database migration check complete")
    except Exception as e:
        print(f"⚠️  DB migration error (non-fatal): {e}")


# ══════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            return jsonify({
                'status': 'success',
                'message': 'Login successful!',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'full_name': user.get('full_name', ''),
                    'email': user.get('email'),
                    'role': user.get('role', 'user')
                }
            })
        else:
            return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# DEPARTMENTS
# ══════════════════════════════════════════════════════════════════

@app.route('/departments', methods=['GET'])
def get_departments():
    try:
        branch_id = request.args.get('branch_id', type=int)
        co_id = request.args.get('co_id', type=int)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        if branch_id:
            cursor.execute("""
                SELECT s.sub_dept_id AS id, s.sub_dept_desc AS name
                FROM sub_dept_mst s
                JOIN dept_mst d ON s.dept_id = d.dept_id
                WHERE d.branch_id = %s
                ORDER BY s.sub_dept_desc
            """, (branch_id,))
        elif co_id:
            cursor.execute("""
                SELECT s.sub_dept_id AS id, s.sub_dept_desc AS name
                FROM sub_dept_mst s
                JOIN dept_mst d ON s.dept_id = d.dept_id
                WHERE d.branch_id IN (SELECT branch_id FROM branch_mst WHERE co_id = %s)
                ORDER BY s.sub_dept_desc
            """, (co_id,))
        else:
            cursor.execute("""
                SELECT sub_dept_id AS id, sub_dept_desc AS name
                FROM sub_dept_mst ORDER BY sub_dept_desc
            """)

        data = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'shifts': data, 'total': len(data)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/departments', methods=['POST'])
def add_department():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'status': 'error', 'message': 'Name is required'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO departments (name) VALUES (%s)", (name,))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'id': new_id, 'message': 'Department added!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# SHIFTS
# ══════════════════════════════════════════════════════════════════

@app.route('/shifts', methods=['GET'])
def get_shifts():
    try:
        branch_id = request.args.get('branch_id', type=int)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        if branch_id:
            cursor.execute("""
                SELECT sm.spell_id AS id, sm.spell_name AS name,
                       sm.starting_time AS start_time, sm.end_time,
                       COALESCE(sm.working_hours, 8.0) AS working_hours
                FROM spell_mst sm
                JOIN shift_mst sh ON sm.shift_id = sh.shift_id
                WHERE sh.branch_id = %s
                ORDER BY sm.spell_name
            """, (branch_id,))
        else:
            cursor.execute("""
                SELECT spell_id AS id, spell_name AS name,
                       starting_time AS start_time, end_time,
                       COALESCE(working_hours, 8.0) AS working_hours
                FROM spell_mst ORDER BY spell_name
            """)

        data = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'shifts': data, 'total': len(data)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/shifts', methods=['POST'])
def add_shift():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        if not name:
            return jsonify({'status': 'error', 'message': 'Name is required'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO spell_mst (spell_name, spell_start_time, spell_end_time) VALUES (%s, %s, %s)",
                       (name, start_time, end_time))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'id': new_id, 'message': 'Shift added!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# OCCUPATIONS (Designations)
# ══════════════════════════════════════════════════════════════════

@app.route('/occupations', methods=['GET'])
def get_occupations():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM occupations ORDER BY name")
        data = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'data': data, 'total': len(data)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/occupations', methods=['POST'])
def add_occupation():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'status': 'error', 'message': 'Occupation name is required!'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO occupations (name) VALUES (%s)", (name,))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'id': new_id, 'message': f"Occupation '{name}' added!"})
    except mysql.connector.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Occupation already exists!'}), 409
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/occupations/<int:occ_id>', methods=['PUT'])
def edit_occupation(occ_id):
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'status': 'error', 'message': 'Occupation name is required!'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE occupations SET name = %s WHERE id = %s", (name, occ_id))
        db.commit()

        if cursor.rowcount == 0:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'Occupation not found!'}), 404

        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': f"Occupation updated to '{name}'!"})
    except mysql.connector.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Occupation name already exists!'}), 409
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/occupations/<int:occ_id>', methods=['DELETE'])
def delete_occupation(occ_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM occupations WHERE id = %s", (occ_id,))
        db.commit()

        if cursor.rowcount == 0:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'Occupation not found!'}), 404

        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Occupation deleted!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# EMPLOYEES - CRUD with Face Registration
# ══════════════════════════════════════════════════════════════════

def generate_face_embedding(image_bytes):
    """Generate 128-d face embedding from image bytes"""
    if not FACE_RECOGNITION_AVAILABLE:
        return None

    temp_path = os.path.join(PHOTO_DIR, '_temp_face.jpg')
    with open(temp_path, 'wb') as f:
        f.write(image_bytes)

    try:
        image = face_recognition.load_image_file(temp_path)
        encodings = face_recognition.face_encodings(image)
        if len(encodings) > 0:
            return encodings[0].tolist()
        else:
            return None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ─── GET /employees ──────────────────────────────────────────────
@app.route('/employees', methods=['GET'])
def get_employees():
    """List all active employees with department, designation, shift names"""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                p.eb_id AS id,
                p.emp_code,
                CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                o.sub_dept_id AS department_id,
                o.designation_id,
                o.branch_id,
                f.photo_html,
                p.active AS is_active,
                p.updated_date_time AS created_at,
                s.sub_dept_desc AS department_name,
                d.desig AS designation_name,
                NULL AS shift_name,
                NULL AS shift_id
            FROM hrms_ed_personal_details p
            INNER JOIN hrms_ed_official_details o ON p.eb_id = o.eb_id
            LEFT JOIN employee_face_mst f ON p.eb_id = f.eb_id
            LEFT JOIN sub_dept_mst s ON o.sub_dept_id = s.sub_dept_id
            LEFT JOIN designation_mst d ON o.designation_id = d.designation_id
            WHERE p.active = 1
            ORDER BY p.first_name, p.last_name
        """)

        employees = cursor.fetchall()

        for emp in employees:
            if emp.get('created_at'):
                emp['created_at'] = emp['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'data': employees,
            'total': len(employees)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── POST /register ───────────────────────────────────────────────
@app.route('/register', methods=['POST'])
def add_employee():
    """Add new employee with optional face photo registration"""
    try:
        data = request.get_json()

        # ── LOG: Show FULL data received from mobile app ─────────
        print("\n" + "=" * 60)
        print("📥 ADD EMPLOYEE - FULL Request Data Received:")
        print("=" * 60)
        # Print all fields except face_image (too long)
        log_data = {k: v for k, v in data.items() if k != 'face_image'}
        print(json.dumps(log_data, indent=2))
        has_face = data.get('face_image') is not None
        face_len = len(data.get('face_image', '') or '')
        print(f"\n  face_image: {'Yes (' + str(face_len) + ' chars)' if has_face else 'No / None'}")
        print("=" * 60 + "\n")
        # ─────────────────────────────────────────────────────────

        emp_code = data.get('emp_code', '').strip()
        name = data.get('name', '').strip()
        department_id = data.get('department_id')  # sub_dept_id
        designation_id = data.get('designation_id')
        shift_id = data.get('shift_id')  # spell_id
        branch_id = data.get('branch_id')
        co_id = data.get('co_id')
        face_image_b64 = data.get('face_image')

        if not emp_code or not name:
            return jsonify({'status': 'error', 'message': 'Employee code and name are required'}), 400

        db = get_db()
        cursor = db.cursor()

        # Check duplicate emp_code
        cursor.execute("SELECT emp_id FROM hrms_ed_personal_details WHERE emp_code = %s", (emp_code,))
        if cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': f'Employee code {emp_code} already exists'}), 400

        # Split name into parts
        name_parts = name.split()
        first_name = name_parts[0] if len(name_parts) > 0 else name
        last_name = name_parts[-1] if len(name_parts) > 1 else ''
        middle_name = ' '.join(name_parts[1:-1]) if len(name_parts) > 2 else None

        # Insert into hrms_ed_personal_details
        cursor.execute("""
            INSERT INTO hrms_ed_personal_details (emp_code, first_name, middle_name, last_name, active, created_date)
            VALUES (%s, %s, %s, %s, 1, NOW())
        """, (emp_code, first_name, middle_name, last_name))
        
        emp_id = cursor.lastrowid

        # Insert into hrms_ed_official_details
        cursor.execute("""
            INSERT INTO hrms_ed_official_details (emp_id, emp_code, sub_dept_id, designation_id, spell_id, branch_id, co_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (emp_id, emp_code, department_id, designation_id, shift_id, branch_id, co_id))

        # Process face image and store in employee_face_mst
        if face_image_b64:
            image_bytes = base64.b64decode(face_image_b64)

            # Generate face embedding for attendance matching
            embedding = generate_face_embedding(image_bytes)
            face_embedding = json.dumps(embedding) if embedding is not None else None
            
            if not face_embedding:
                print(f"⚠️  No face detected in image for {emp_code}")

            # Store in employee_face_mst
            cursor.execute("""
                INSERT INTO employee_face_mst (emp_code, face_image, face_encoding, created_date)
                VALUES (%s, %s, %s, NOW())
            """, (emp_code, face_image_b64, face_embedding))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'id': emp_id,
            'message': 'Employee added successfully!'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── PUT /employees/<id> ─────────────────────────────────────────
@app.route('/employees/<int:emp_id>', methods=['PUT'])
def update_employee(emp_id):
    """Update employee, optionally re-register face"""
    try:
        data = request.get_json()

        emp_code = data.get('emp_code', '').strip()
        name = data.get('name', '').strip()
        department_id = data.get('department_id')
        designation_id = data.get('designation_id')
        shift_id = data.get('shift_id')
        face_image_b64 = data.get('face_image')

        if not emp_code or not name:
            return jsonify({'status': 'error', 'message': 'Employee code and name are required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM employees WHERE id = %s", (emp_id,))
        existing = cursor.fetchone()
        if not existing:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        # Check duplicate emp_code (excluding current)
        cursor.execute("SELECT id FROM employees WHERE emp_code = %s AND id != %s", (emp_code, emp_id))
        if cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': f'Employee code {emp_code} already exists'}), 400

        photo_html = existing.get('photo_html')
        face_embedding = existing.get('face_embedding')

        if face_image_b64:
            image_bytes = base64.b64decode(face_image_b64)

            # Store photo as HTML (base64 embedded) — no physical file saved
            photo_html = f'<img src="data:image/jpeg;base64,{face_image_b64}" />'

            # Regenerate face embedding
            embedding = generate_face_embedding(image_bytes)
            if embedding is not None:
                face_embedding = json.dumps(embedding)

        cursor.execute("""
            UPDATE employees
            SET emp_code = %s, name = %s, department_id = %s, designation_id = %s,
                shift_id = %s, face_embedding = %s, photo_html = %s
            WHERE id = %s
        """, (emp_code, name, department_id, designation_id, shift_id,
              face_embedding, photo_html, emp_id))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'message': 'Employee updated successfully!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── DELETE /employees/<id> ───────────────────────────────────────
@app.route('/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    """Soft delete employee (set is_active = 0)"""
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM employees WHERE id = %s", (emp_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        cursor.execute("UPDATE employees SET is_active = 0 WHERE id = %s", (emp_id,))
        db.commit()
        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'message': 'Employee deleted successfully!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# GET EMPLOYEE BY CODE - Lookup employee by emp_code
# ══════════════════════════════════════════════════════════════════

@app.route('/employee/<emp_code>', methods=['GET'])
def get_employee_by_code(emp_code):
    """
    Lookup employee by emp_code with optional branch_id filter.
    Query params:
      ?branch_id=29 (optional) - Filter by branch
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Build query with optional branch_id filter
        if branch_id:
            cursor.execute("""
                SELECT p.eb_id AS id, o.emp_code,
                       CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                       f.photo_html, o.branch_id
                FROM hrms_ed_personal_details p
                INNER JOIN hrms_ed_official_details o ON p.eb_id = o.eb_id
                LEFT JOIN employee_face_mst f ON p.eb_id = f.eb_id
                WHERE o.emp_code = %s AND p.active = 1 AND o.branch_id = %s
                LIMIT 1
            """, (emp_code, branch_id))
        else:
            cursor.execute("""
                SELECT p.eb_id AS id, o.emp_code,
                       CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                       f.photo_html, o.branch_id
                FROM hrms_ed_personal_details p
                INNER JOIN hrms_ed_official_details o ON p.eb_id = o.eb_id
                LEFT JOIN employee_face_mst f ON p.eb_id = f.eb_id
                WHERE o.emp_code = %s AND p.active = 1
                LIMIT 1
            """, (emp_code,))
        
        employee = cursor.fetchone()
        cursor.close()
        db.close()

        if employee:
            return jsonify({
                'status': 'success',
                'emp_code': employee['emp_code'],
                'emp_name': employee['name'].strip(),
                'photo_html': employee.get('photo_html'),
                'branch_id': employee.get('branch_id'),
                'message': f"Employee found: {employee['name'].strip()}"
            })
        else:
            branch_msg = f" in branch {branch_id}" if branch_id else ""
            return jsonify({
                'status': 'error',
                'message': f'Employee with code {emp_code}{branch_msg} not found or inactive'
            }), 404

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# SEARCH EMPLOYEES - Search by name or code (partial match)
# ══════════════════════════════════════════════════════════════════

@app.route('/employees/search', methods=['GET'])
def search_employees():
    """Search employees by name or emp_code (partial match)."""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'status': 'error', 'message': 'Search query is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        search_pattern = f'%{query}%'
        cursor.execute("""
            SELECT p.eb_id AS id, o.emp_code,
                   TRIM(CONCAT(COALESCE(p.first_name,''), ' ',
                               COALESCE(p.middle_name,''), ' ',
                               COALESCE(p.last_name,''))) AS name,
                   o.branch_id, o.sub_dept_id AS department_id,
                   o.designation_id, o.spell_id AS shift_id,
                   NULL AS photo_html
            FROM hrms_ed_personal_details p
            INNER JOIN hrms_ed_official_details o ON p.eb_id = o.eb_id
            WHERE (p.active IS NULL OR p.active != 0)
              AND (o.emp_code LIKE %s
                   OR p.first_name  LIKE %s
                   OR p.last_name   LIKE %s
                   OR CONCAT(p.first_name,' ',COALESCE(p.last_name,'')) LIKE %s)
            ORDER BY p.first_name
            LIMIT 20
        """, (search_pattern, search_pattern, search_pattern, search_pattern))
        employees = cursor.fetchall()
        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'data': employees,
            'total': len(employees)
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# CHECK FACE - Identify employee only (no attendance saved)
# ══════════════════════════════════════════════════════════════════

@app.route('/check-face', methods=['POST'])
def check_face():
    """
    Receives base64 face image, compares against all registered employees'
    face_embeddings, returns matching employee info + photo_html.
    Does NOT mark attendance.
    """
    try:
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'face_recognition library not installed on server'
            }), 500

        data = request.get_json()
        face_image_b64 = data.get('image')

        if not face_image_b64:
            return jsonify({'status': 'error', 'message': 'No image provided'}), 400

        # Decode and get face encoding from uploaded image
        image_bytes = base64.b64decode(face_image_b64)
        temp_path = os.path.join(PHOTO_DIR, '_temp_check.jpg')
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)

        try:
            image = face_recognition.load_image_file(temp_path)
            unknown_encodings = face_recognition.face_encodings(image)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if len(unknown_encodings) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No face detected in the image'
            }), 400

        unknown_encoding = unknown_encodings[0]

        # Load face embeddings from employee_face_mst joined with hrms_ed_personal_details
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.eb_id, p.emp_code,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                   f.face_embedding, f.photo_html
            FROM employee_face_mst f
            JOIN hrms_ed_personal_details p ON f.eb_id = p.eb_id
            WHERE f.active = 1 AND p.active = 1 AND f.face_embedding IS NOT NULL
        """)
        employees = cursor.fetchall()
        cursor.close()
        db.close()

        # Compare against each employee
        best_match = None
        best_distance = 1.0

        for emp in employees:
            try:
                known_encoding = np.array(json.loads(emp['face_embedding']))
                distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]

                if distance < best_distance and distance < 0.6:
                    best_distance = distance
                    best_match = emp
            except Exception:
                continue

        if best_match:
            photo_html_val = best_match.get('photo_html')
            print(f"\n✅ Face matched: {best_match['name']} (code={best_match['emp_code']})")
            print(f"   photo_html: {'Yes (' + str(len(photo_html_val)) + ' chars)' if photo_html_val else 'None / Empty'}")

            return jsonify({
                'status': 'success',
                'emp_code': best_match['emp_code'],
                'emp_name': best_match['name'],
                'photo_html': photo_html_val,
                'confidence': round((1 - best_distance) * 100, 2),
                'message': f"Face matched: {best_match['name']}"
            })
        else:
            print("\n❌ No face match found")
            return jsonify({
                'status': 'error',
                'message': 'Face not recognized. No matching employee found.'
            }, 404)

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# ATTENDANCE - Face Recognition Matching (marks attendance)
# ══════════════════════════════════════════════════════════════════

@app.route('/attendance', methods=['POST'])
def check_attendance_face():
    """
    Receives base64 face image, matches against employee_face_mst,
    marks attendance in daily_attendance table.
    """
    try:
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({'status': 'error', 'message': 'face_recognition library not installed on server'}), 500

        data = request.get_json()
        face_image_b64 = data.get('image')
        att_type = data.get('att_type', 'R')
        department_id = data.get('department_id')
        shift_id = data.get('shift_id')
        designation_id = data.get('designation_id')
        shift_hours = data.get('shift_hours', 0)
        working_hours = data.get('working_hours', 0)
        idle_hours = data.get('idle_hours', 0)
        attendance_date_str = data.get('attendance_date')

        if not face_image_b64:
            return jsonify({'status': 'error', 'message': 'No image provided'}), 400

        image_bytes = base64.b64decode(face_image_b64)
        temp_path = os.path.join(PHOTO_DIR, '_temp_attendance.jpg')
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)

        try:
            image = face_recognition.load_image_file(temp_path)
            unknown_encodings = face_recognition.face_encodings(image)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if len(unknown_encodings) == 0:
            return jsonify({'status': 'error', 'message': 'No face detected in the image'}), 400

        unknown_encoding = unknown_encodings[0]

        # Load face embeddings from employee_face_mst joined with hrms_ed_personal_details
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.eb_id, p.emp_code,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                   f.face_embedding, f.photo_html,
                   o.branch_id
            FROM employee_face_mst f
            JOIN hrms_ed_personal_details p ON f.eb_id = p.eb_id
            LEFT JOIN hrms_ed_official_details o ON p.eb_id = o.eb_id
            WHERE f.active = 1 AND p.active = 1 AND f.face_embedding IS NOT NULL
        """)
        employees = cursor.fetchall()

        best_match = None
        best_distance = 1.0

        for emp in employees:
            try:
                known_encoding = np.array(json.loads(emp['face_embedding']))
                distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
                if distance < best_distance and distance < 0.6:
                    best_distance = distance
                    best_match = emp
            except Exception:
                continue

        if best_match:
            now = datetime.now()
            if attendance_date_str:
                try:
                    att_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
                except ValueError:
                    att_date = now.date()
            else:
                att_date = now.date()

            # Get spell name
            spell_name = None
            if shift_id:
                cursor.execute("SELECT spell_name FROM spell_mst WHERE spell_id = %s", (shift_id,))
                spell_row = cursor.fetchone()
                spell_name = spell_row['spell_name'] if spell_row else None

            branch_id = best_match.get('branch_id')

            cursor.execute("""
                INSERT INTO daily_attendance (
                    attendance_date, attendance_mark, attendance_source, attendance_type,
                    branch_id, eb_id, entry_time, idle_hours, is_active,
                    spell, spell_hours, worked_department_id, worked_designation_id,
                    working_hours, update_date_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (att_date, 'P', 'Face', att_type,
                  branch_id, best_match['eb_id'], now, idle_hours, 1,
                  spell_name, shift_hours, department_id, designation_id,
                  working_hours, now))
            
            attendance_id = cursor.lastrowid
            
            # Save machine data to daily_ebmc_attendance if machines are provided
            machine_ids = data.get('machine_ids', [])
            if machine_ids and isinstance(machine_ids, list):
                for machine_id in machine_ids:
                    cursor.execute("""
                        INSERT INTO daily_ebmc_attendance (
                            daily_atten_id, eb_id, mech_id, attendance_date, 
                            branch_id, is_active, update_date_time
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (attendance_id, best_match['eb_id'], machine_id, att_date, 
                          branch_id, 1, now))
            
            db.commit()
            cursor.close()
            db.close()

            emp_name = best_match['name'].strip()
            return jsonify({
                'status': 'success',
                'emp_code': best_match['emp_code'],
                'emp_name': emp_name,
                'photo_html': best_match.get('photo_html'),
                'confidence': round((1 - best_distance) * 100, 2),
                'message': f"Attendance marked for {emp_name}"
            })
        else:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'Face not recognized. No matching employee found.'}), 404

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# MARK ATTENDANCE - Manual (no face recognition, just emp_code)
# ══════════════════════════════════════════════════════════════════

@app.route('/mark-attendance', methods=['POST'])
def mark_attendance_manual():
    """
    Marks attendance manually using employee code.
    Inserts into daily_attendance table.
    """
    try:
        data = request.get_json()
        emp_code = data.get('emp_code', '').strip()
        status = data.get('status', 'Manual')
        att_type = data.get('att_type', 'R')
        department_id = data.get('department_id')
        shift_id = data.get('shift_id')       # spell_id
        designation_id = data.get('designation_id')
        shift_hours = data.get('shift_hours', 0)
        working_hours = data.get('working_hours', 0)
        idle_hours = data.get('idle_hours', 0)
        attendance_date_str = data.get('attendance_date')

        if not emp_code:
            return jsonify({'status': 'error', 'message': 'Employee code is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Verify employee exists using hrms_ed_personal_details
        cursor.execute("""
            SELECT p.eb_id, p.emp_code,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                   o.branch_id,
                   f.photo_html
            FROM hrms_ed_personal_details p
            INNER JOIN hrms_ed_official_details o ON p.eb_id = o.eb_id AND o.emp_code = p.emp_code
            LEFT JOIN employee_face_mst f ON p.eb_id = f.eb_id
            WHERE p.emp_code = %s AND p.active = 1
            LIMIT 1
        """, (emp_code,))
        employee = cursor.fetchone()

        if not employee:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': f'Employee {emp_code} not found or inactive'}), 404

        # Get spell name from spell_id
        spell_name = None
        if shift_id:
            cursor.execute("SELECT spell_name FROM spell_mst WHERE spell_id = %s", (shift_id,))
            spell_row = cursor.fetchone()
            spell_name = spell_row['spell_name'] if spell_row else None

        now = datetime.now()
        if attendance_date_str:
            try:
                att_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
            except ValueError:
                att_date = now.date()
        else:
            att_date = now.date()

        branch_id = employee.get('branch_id')

        cursor.execute("""
            INSERT INTO daily_attendance (
                attendance_date, attendance_mark, attendance_source, attendance_type,
                branch_id, eb_id, entry_time, idle_hours, is_active,
                spell, spell_hours, worked_department_id, worked_designation_id,
                working_hours, update_date_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (att_date, 'P', status, att_type,
              branch_id, employee['eb_id'], now, idle_hours, 1,
              spell_name, shift_hours, department_id, designation_id,
              working_hours, now))
        
        attendance_id = cursor.lastrowid
        
        # Save machine data to daily_ebmc_attendance if machines are provided
        machine_ids = data.get('machine_ids', [])
        if machine_ids and isinstance(machine_ids, list):
            for machine_id in machine_ids:
                cursor.execute("""
                    INSERT INTO daily_ebmc_attendance (
                        daily_atten_id, eb_id, mech_id, attendance_date, 
                        branch_id, is_active, update_date_time
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (attendance_id, employee['eb_id'], machine_id, att_date, 
                      branch_id, 1, now))
        
        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'emp_code': employee['emp_code'],
            'emp_name': employee['name'].strip(),
            'photo_html': employee.get('photo_html'),
            'message': f"Attendance marked for {employee['name'].strip()} ({status})"
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# DASHBOARD STATS
# ══════════════════════════════════════════════════════════════════

@app.route('/dashboard-stats', methods=['GET'])
def dashboard_stats():
    """
    Returns dashboard statistics for a given date.
    Query params: 
      - date (yyyy-MM-dd) — defaults to today
      - branch_id (int) — filter by branch
      - co_id (int) — filter by company
    """
    try:
        stat_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        branch_id = request.args.get('branch_id', type=int)
        co_id = request.args.get('co_id', type=int)
        spell_id = request.args.get('spell_id', type=int)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Total departments (sub_dept_mst) - filtered by branch
        if branch_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM sub_dept_mst sdm 
                LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id 
                WHERE dm.branch_id = %s
            """, (branch_id,))
        elif co_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM sub_dept_mst sdm 
                LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id 
                WHERE dm.co_id = %s
            """, (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM sub_dept_mst")
        
        total_departments = cursor.fetchone()['cnt']

        # Total designations (filtered by branch if provided)
        desig_query = "SELECT COUNT(DISTINCT designation_id) AS cnt FROM designation_mst WHERE active = 1"
        if branch_id:
            desig_query += " AND branch_id = %s"
            cursor.execute(desig_query, (branch_id,))
        elif co_id:
            desig_query += " AND co_id = %s"
            cursor.execute(desig_query, (co_id,))
        else:
            cursor.execute(desig_query)
        total_designations = cursor.fetchone()['cnt']

        # Total shifts (spell_mst) - filtered by branch via shift_mst
        if branch_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM spell_mst sm 
                LEFT JOIN shift_mst sm2 ON sm.shift_id = sm2.shift_id 
                WHERE sm2.branch_id = %s
            """, (branch_id,))
        elif co_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM spell_mst sm 
                LEFT JOIN shift_mst sm2 ON sm.shift_id = sm2.shift_id 
                WHERE sm2.co_id = %s
            """, (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM spell_mst")
        total_shifts = cursor.fetchone()['cnt']

        # Total employees (filtered by branch/company from hrms_ed_official_details)
        if branch_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE branch_id = %s",
                (branch_id,)
            )
        elif co_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE co_id = %s",
                (co_id,)
            )
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM hrms_ed_official_details")
        total_employees = cursor.fetchone()['cnt']

        # Resolve spell name from spell_id for filtering
        spell_name_filter = None
        if spell_id:
            cursor.execute("SELECT spell_name FROM spell_mst WHERE spell_id = %s", (spell_id,))
            row = cursor.fetchone()
            spell_name_filter = row['spell_name'] if row else None

        # Present on that date — daily_attendance has branch_id directly
        present_query = """
            SELECT COUNT(*) AS cnt
            FROM daily_attendance da
            WHERE da.attendance_date = %s
        """
        present_params = [stat_date]
        if branch_id:
            present_query += " AND da.branch_id = %s"
            present_params.append(branch_id)
        elif co_id:
            present_query += " AND da.co_id = %s"
            present_params.append(co_id)
        if spell_name_filter:
            present_query += " AND da.spell = %s"
            present_params.append(spell_name_filter)
        cursor.execute(present_query, tuple(present_params))
        total_present = cursor.fetchone()['cnt']

        # Present by Face
        face_query = """
            SELECT COUNT(*) AS cnt
            FROM daily_attendance da
            WHERE da.attendance_date = %s AND da.attendance_source = 'Face'
        """
        face_params = [stat_date]
        if branch_id:
            face_query += " AND da.branch_id = %s"
            face_params.append(branch_id)
        elif co_id:
            face_query += " AND da.co_id = %s"
            face_params.append(co_id)
        if spell_name_filter:
            face_query += " AND da.spell = %s"
            face_params.append(spell_name_filter)
        cursor.execute(face_query, tuple(face_params))
        present_face = cursor.fetchone()['cnt']

        # Present by Manual
        manual_query = """
            SELECT COUNT(*) AS cnt
            FROM daily_attendance da
            WHERE da.attendance_date = %s AND da.attendance_source = 'Manual'
        """
        manual_params = [stat_date]
        if branch_id:
            manual_query += " AND da.branch_id = %s"
            manual_params.append(branch_id)
        elif co_id:
            manual_query += " AND da.co_id = %s"
            manual_params.append(co_id)
        if spell_name_filter:
            manual_query += " AND da.spell = %s"
            manual_params.append(spell_name_filter)
        cursor.execute(manual_query, tuple(manual_params))
        present_manual = cursor.fetchone()['cnt']

        # Absent = total employees - those present on that date+branch (ignoring spell)
        absent_query = """
            SELECT COUNT(DISTINCT da.eb_id) AS cnt
            FROM daily_attendance da
            WHERE da.attendance_date = %s
        """
        absent_params = [stat_date]
        if branch_id:
            absent_query += " AND da.branch_id = %s"
            absent_params.append(branch_id)
        elif co_id:
            absent_query += " AND da.co_id = %s"
            absent_params.append(co_id)
        cursor.execute(absent_query, tuple(absent_params))
        present_for_absent = cursor.fetchone()['cnt']
        total_absent = max(0, total_employees - present_for_absent)

        # Department-wise statistics (filtered by branch)
        # Query to get department data with present count based on worked_department_id
        dept_stats_query = """
            SELECT 
                sdm.sub_dept_id AS department_id,
                sdm.sub_dept_desc AS department_name,
                0 AS total_employees,
                COUNT(da.eb_id) AS present
            FROM sub_dept_mst sdm
            LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
            LEFT JOIN daily_attendance da 
                ON da.worked_department_id = sdm.sub_dept_id 
                AND da.attendance_date = %s
                AND (da.is_active IS NULL OR da.is_active = 1)
        """
        dept_stats_params = [stat_date]

        if spell_name_filter:
            dept_stats_query = dept_stats_query.rstrip() + "\n                AND da.spell = %s\n        "
            dept_stats_params.append(spell_name_filter)

        if branch_id:
            dept_stats_query += " WHERE dm.branch_id = %s"
            dept_stats_params.append(branch_id)
        elif co_id:
            dept_stats_query += " WHERE dm.co_id = %s"
            dept_stats_params.append(co_id)
        
        dept_stats_query += " GROUP BY sdm.sub_dept_id, sdm.sub_dept_desc ORDER BY sdm.sub_dept_desc"

        print(f"Executing dept_stats query with params: {dept_stats_params}")
        cursor.execute(dept_stats_query, tuple(dept_stats_params))
        dept_stats = cursor.fetchall()
        print(f"Department-wise query results: {dept_stats}")

        # Create three lists:
        # 1. department_wise: All departments (for backwards compatibility)
        # 2. department_present: Only departments with present > 0
        # 3. department_master: All departments with employees > 0
        department_wise = []
        department_present = []
        department_master = []
        
        for dept in dept_stats:
            present_count = int(dept['present'])
            total_emp = dept['total_employees']
            absent_count = max(0, total_emp - present_count)

            dept_obj = {
                'department_id': dept['department_id'],
                'department_name': dept['department_name'],
                'total_employees': total_emp,
                'present': present_count,
                'absent': absent_count
            }
            
            # Add to all departments list
            department_wise.append(dept_obj)
            
            # Add to department_present only if present > 0
            if present_count > 0:
                department_present.append(dept_obj)
            
            # Add to department_master if has employees
            if total_emp > 0:
                department_master.append(dept_obj)

        print(f"department_wise: {len(department_wise)} items - {department_wise}")
        print(f"department_present: {len(department_present)} items - {department_present}")
        print(f"department_master: {len(department_master)} items - {department_master}")

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'date': stat_date,
            'total_departments': total_departments,
            'total_designations': total_designations,
            'total_shifts': total_shifts,
            'total_employees': total_employees,
            'total_present': total_present,
            'present_face': present_face,
            'present_manual': present_manual,
            'total_absent': total_absent,
            'department_wise': department_wise,
            'department_present': department_present,
            'department_master': department_master
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# ATTENDANCE DASHBOARD (Charts)
# ══════════════════════════════════════════════════════════════════

@app.route('/attendance-dashboard', methods=['GET'])
def attendance_dashboard():
    """
    Returns chart data for the Attendance Dashboard screen.
    Query params: date, branch_id, co_id, spell_id
    """
    try:
        from datetime import timedelta as _td
        stat_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        branch_id = request.args.get('branch_id', type=int)
        co_id     = request.args.get('co_id',     type=int)
        spell_id  = request.args.get('spell_id',  type=int)

        db     = get_db()
        cursor = db.cursor(dictionary=True)

        # Resolve spell name
        spell_name_filter = None
        if spell_id:
            cursor.execute("SELECT spell_name FROM spell_mst WHERE spell_id = %s", (spell_id,))
            row = cursor.fetchone()
            spell_name_filter = row['spell_name'] if row else None

        def branch_clause(alias='da'):
            clauses, params = [], []
            if branch_id:
                clauses.append(f"{alias}.branch_id = %s"); params.append(branch_id)
            if spell_name_filter:
                clauses.append(f"{alias}.spell = %s"); params.append(spell_name_filter)
            return clauses, params

        # 1. Today's attendance counts (present / absent)
        base_c, base_p = branch_clause()
        where = ("AND " + " AND ".join(base_c)) if base_c else ""
        cursor.execute(f"""
            SELECT COUNT(DISTINCT da.eb_id) AS present
            FROM daily_attendance da
            WHERE da.attendance_date = %s AND (da.is_active IS NULL OR da.is_active = 1) {where}
        """, tuple([stat_date] + base_p))
        present_today = cursor.fetchone()['present']

        # Total employees for absent calculation
        if branch_id:
            cursor.execute("SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE branch_id = %s AND (active IS NULL OR active != 0)", (branch_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE (active IS NULL OR active != 0)")
        total_employees = cursor.fetchone()['cnt']
        absent_today = max(0, total_employees - present_today)

        today_attendance = {
            'present': present_today,
            'absent': absent_today,
            'leave': 0,
            'total_employees': total_employees
        }

        # 2. Last 7 days present count
        last7 = []
        try:
            d = datetime.strptime(stat_date, '%Y-%m-%d')
        except Exception:
            d = datetime.now()
        for i in range(6, -1, -1):
            day = d - _td(days=i)
            day_str = day.strftime('%Y-%m-%d')
            bc, bp = branch_clause()
            wh = ("AND " + " AND ".join(bc)) if bc else ""
            cursor.execute(f"""
                SELECT COUNT(DISTINCT da.eb_id) AS cnt
                FROM daily_attendance da
                WHERE da.attendance_date = %s AND (da.is_active IS NULL OR da.is_active = 1) {wh}
            """, tuple([day_str] + bp))
            cnt = cursor.fetchone()['cnt']
            last7.append({'date': day_str, 'label': day.strftime('%d-%b'), 'present': cnt})

        # 3. Wages last 7 days (sum of working_hours as proxy)
        wages7 = []
        for item in last7:
            bc, bp = branch_clause()
            wh = ("AND " + " AND ".join(bc)) if bc else ""
            cursor.execute(f"""
                SELECT COALESCE(SUM(da.working_hours), 0) AS total_hours
                FROM daily_attendance da
                WHERE da.attendance_date = %s AND (da.is_active IS NULL OR da.is_active = 1) {wh}
            """, tuple([item['date']] + bp))
            hrs = float(cursor.fetchone()['total_hours'] or 0)
            wages7.append({'date': item['date'], 'label': item['label'], 'total_hours': hrs, 'amount': hrs})

        # 4. Absent buckets — employees absent for N consecutive days up to stat_date
        absent_buckets = {'range_1_to_7': 0, 'range_8_to_15': 0, 'range_16_to_30': 0, 'over_30_days': 0}
        try:
            bc, bp = branch_clause()
            emp_where = ("AND " + " AND ".join(bc).replace('da.branch_id', 'o.branch_id').replace('da.spell', '1=1')) if bc else ""
            cursor.execute(f"""
                SELECT o.eb_id
                FROM hrms_ed_official_details o
                WHERE (o.active IS NULL OR o.active != 0)
                  {emp_where if branch_id else ''}
            """, tuple(bp[:1] if branch_id else []))
            all_emps = [r['eb_id'] for r in cursor.fetchall()]

            # Get last attendance date per employee
            bc2, bp2 = branch_clause()
            wh2 = ("AND " + " AND ".join(bc2)) if bc2 else ""
            cursor.execute(f"""
                SELECT da.eb_id, MAX(da.attendance_date) AS last_att
                FROM daily_attendance da
                WHERE da.attendance_date <= %s AND (da.is_active IS NULL OR da.is_active = 1) {wh2}
                GROUP BY da.eb_id
            """, tuple([stat_date] + bp2))
            last_att_map = {r['eb_id']: r['last_att'] for r in cursor.fetchall()}

            stat_d = datetime.strptime(stat_date, '%Y-%m-%d').date()
            for eb in all_emps:
                la = last_att_map.get(eb)
                if la is None:
                    diff = 999
                else:
                    la_d = la if hasattr(la, 'year') else datetime.strptime(str(la), '%Y-%m-%d').date()
                    diff = (stat_d - la_d).days
                if 1 <= diff <= 7:
                    absent_buckets['range_1_to_7'] += 1
                elif 8 <= diff <= 15:
                    absent_buckets['range_8_to_15'] += 1
                elif 16 <= diff <= 30:
                    absent_buckets['range_16_to_30'] += 1
                elif diff > 30:
                    absent_buckets['over_30_days'] += 1
        except Exception as bucket_err:
            print(f"[ATT-DASH] absent buckets error: {bucket_err}")

        # 5. Man vs Machine last 7 days
        man_machine = []
        for item in last7:
            bc, bp = branch_clause()
            wh = ("AND " + " AND ".join(bc)) if bc else ""
            cursor.execute(f"""
                SELECT COUNT(DISTINCT da.eb_id) AS total_hands
                FROM daily_attendance da
                WHERE da.attendance_date = %s AND (da.is_active IS NULL OR da.is_active = 1) {wh}
            """, tuple([item['date']] + bp))
            hands = float(cursor.fetchone()['total_hands'] or 0)
            cursor.execute(f"""
                SELECT COUNT(DISTINCT dea.mc_id) AS mc_cnt
                FROM daily_ebmc_attendance dea
                JOIN daily_attendance da ON dea.daily_atten_id = da.daily_atten_id
                WHERE da.attendance_date = %s AND (dea.is_active IS NULL OR dea.is_active = 1) {wh}
            """, tuple([item['date']] + bp))
            mc_row = cursor.fetchone()
            mc_cnt = float(mc_row['mc_cnt'] or 0) if mc_row else 0.0
            man_machine.append({'date': item['date'], 'label': item['label'],
                                 'total_hands': hands, 'total_target': mc_cnt})

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'date': stat_date,
            'branch_id': branch_id,
            'co_id': co_id,
            'today_attendance': today_attendance,
            'wages_last_7_days': wages7,
            'last_7_days_present': last7,
            'absent_buckets': absent_buckets,
            'man_machine_last_7_days': man_machine
        })
    except Exception as e:
        print(f"[ATT-DASH] error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# ATTENDANCE REPORT
# ══════════════════════════════════════════════════════════════════

@app.route('/attendance-report', methods=['GET'])
def attendance_report():
    """
    Returns attendance records from daily_attendance with filters.
    Query params: date, emp_code, emp_name, shift_name, branch_id
    """
    try:
        attendance_date = request.args.get('date')
        emp_code = request.args.get('emp_code', '').strip()
        emp_name = request.args.get('emp_name', '').strip()
        shift_name = request.args.get('shift_name', '').strip()
        branch_id = request.args.get('branch_id', type=int)

        if not attendance_date:
            return jsonify({'status': 'error', 'message': 'date parameter is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT da.daily_atten_id AS id,
                   p.emp_code,
                   p.eb_id,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS emp_name,
                   COALESCE(s.sub_dept_desc, '') AS department_name,
                   COALESCE(d.desig, '') AS designation_name,
                   COALESCE(da.spell, '') AS shift_name,
                   da.attendance_date,
                   TIME(da.entry_time) AS attendance_time,
                   da.attendance_source AS status,
                   da.attendance_type AS att_type,
                   COALESCE(da.spell_hours, 0) AS shift_hours,
                   COALESCE(da.working_hours, 0) AS working_hours,
                   COALESCE(da.idle_hours, 0) AS idle_hours
            FROM daily_attendance da
            JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
            LEFT JOIN sub_dept_mst s ON da.worked_department_id = s.sub_dept_id
            LEFT JOIN designation_mst d ON da.worked_designation_id = d.designation_id
            WHERE da.attendance_date = %s AND (da.is_active IS NULL OR da.is_active = 1)
        """
        params = [attendance_date]

        if branch_id:
            sql += " AND da.branch_id = %s"
            params.append(branch_id)


        if emp_code:
            sql += " AND p.emp_code LIKE %s"
            params.append(f"%{emp_code}%")

        if emp_name:
            sql += " AND (p.first_name LIKE %s OR p.middle_name LIKE %s OR p.last_name LIKE %s)"
            params.extend([f"%{emp_name}%", f"%{emp_name}%", f"%{emp_name}%"])

        if shift_name and shift_name != "All Shifts":
            sql += " AND da.spell = %s"
            params.append(shift_name)

        sql += " ORDER BY da.attendance_date DESC, da.entry_time DESC"

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        data = []
        for row in rows:
            # Fetch machine numbers for this attendance record
            cursor.execute("""
                SELECT mm.mech_code, mm.machine_name
                FROM daily_ebmc_attendance dea
                JOIN machine_mst mm ON dea.mech_id = mm.machine_id
                WHERE dea.daily_atten_id = %s AND (dea.is_active IS NULL OR dea.is_active = 1)
                ORDER BY mm.mech_code
            """, (row['id'],))
            machine_rows = cursor.fetchall()
            
            # Create comma-separated list of machine codes
            machine_nos = ', '.join([m['mech_code'] or '' for m in machine_rows if m['mech_code']])
            
            data.append({
                'id': row['id'],
                'emp_code': row['emp_code'],
                'eb_id': row['eb_id'],
                'emp_name': (row['emp_name'] or '').strip(),
                'department_name': row['department_name'] or '',
                'designation_name': row['designation_name'] or '',
                'shift_name': row['shift_name'] or '',
                'attendance_date': str(row['attendance_date']),
                'attendance_time': str(row['attendance_time']),
                'status': row['status'] or '',
                'att_type': row['att_type'] or 'R',
                'shift_hours': float(row['shift_hours']),
                'working_hours': float(row['working_hours']),
                'idle_hours': float(row['idle_hours']),
                'photo_att': '',
                'machine_nos': machine_nos
            })

        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'data': data, 'total': len(data)})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# UPDATE ATTENDANCE - Update existing attendance record
# ══════════════════════════════════════════════════════════════════

@app.route('/attendance/<int:attendance_id>', methods=['PUT'])
def update_attendance(attendance_id):
    """
    Update an existing attendance record.
    Path param: attendance_id (daily_atten_id)
    Request body: JSON with fields to update
    """
    try:
        data = request.get_json()
        
        # Extract fields
        emp_code = data.get('emp_code', '').strip()
        attendance_date_str = data.get('attendance_date')
        att_type = data.get('att_type', 'R')
        department_id = data.get('department_id')
        shift_id = data.get('shift_id')
        designation_id = data.get('designation_id')
        shift_hours = data.get('shift_hours', 0)
        working_hours = data.get('working_hours', 0)
        idle_hours = data.get('idle_hours', 0)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Get spell name from spell_id if provided
        spell_name = None
        if shift_id:
            cursor.execute("SELECT spell_name FROM spell_mst WHERE spell_id = %s", (shift_id,))
            spell_row = cursor.fetchone()
            spell_name = spell_row['spell_name'] if spell_row else None

        # Parse attendance date
        if attendance_date_str:
            try:
                att_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
            except ValueError:
                att_date = datetime.now().date()
        else:
            att_date = datetime.now().date()

        now = datetime.now()

        # Update the attendance record
        update_sql = """
            UPDATE daily_attendance
            SET attendance_date = %s,
                attendance_type = %s,
                worked_department_id = %s,
                worked_designation_id = %s,
                spell = %s,
                spell_hours = %s,
                working_hours = %s,
                idle_hours = %s,
                update_date_time = %s
            WHERE daily_atten_id = %s
        """
        
        cursor.execute(update_sql, (
            att_date,
            att_type,
            department_id,
            designation_id,
            spell_name,
            shift_hours,
            working_hours,
            idle_hours,
            now,
            attendance_id
        ))
        
        db.commit()

        if cursor.rowcount == 0:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': f'Attendance record {attendance_id} not found'}), 404

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'message': f'Attendance record updated successfully',
            'attendance_id': attendance_id
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# GET SINGLE ATTENDANCE - Get attendance record by ID
# ══════════════════════════════════════════════════════════════════

@app.route('/attendance/<int:attendance_id>', methods=['GET'])
def get_attendance_by_id(attendance_id):
    """
    Get a single attendance record by ID.
    Path param: attendance_id (daily_atten_id)
    """
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT da.daily_atten_id AS id,
                   da.eb_id,
                   p.emp_code,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS emp_name,
                   da.attendance_date,
                   da.attendance_type AS att_type,
                   da.attendance_source AS status,
                   da.worked_department_id AS department_id,
                   da.worked_designation_id AS designation_id,
                   COALESCE(da.spell, '') AS shift_name,
                   COALESCE(da.spell_hours, 0) AS shift_hours,
                   COALESCE(da.working_hours, 0) AS working_hours,
                   COALESCE(da.idle_hours, 0) AS idle_hours,
                   da.branch_id,
                   f.photo_html
            FROM daily_attendance da
            JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
            LEFT JOIN employee_face_mst f ON da.eb_id = f.eb_id
            WHERE da.daily_atten_id = %s AND (da.is_active IS NULL OR da.is_active = 1)
            LIMIT 1
        """
        
        cursor.execute(sql, (attendance_id,))
        row = cursor.fetchone()

        cursor.close()
        db.close()

        if not row:
            return jsonify({'status': 'error', 'message': f'Attendance record {attendance_id} not found'}), 404

        # Find shift_id by matching spell_name
        shift_id = None
        if row['shift_name']:
            db2 = get_db()
            cursor2 = db2.cursor(dictionary=True)
            cursor2.execute("SELECT spell_id FROM spell_mst WHERE spell_name = %s LIMIT 1", (row['shift_name'],))
            shift_row = cursor2.fetchone()
            if shift_row:
                shift_id = shift_row['spell_id']
            cursor2.close()
            db2.close()

        data = {
            'id': row['id'],
            'eb_id': row['eb_id'],
            'emp_code': row['emp_code'],
            'emp_name': (row['emp_name'] or '').strip(),
            'attendance_date': str(row['attendance_date']),
            'att_type': row['att_type'] or 'R',
            'status': row['status'] or 'Manual',
            'department_id': row['department_id'],
            'designation_id': row['designation_id'],
            'shift_id': shift_id,
            'shift_name': row['shift_name'],
            'shift_hours': float(row['shift_hours']),
            'working_hours': float(row['working_hours']),
            'idle_hours': float(row['idle_hours']),
            'branch_id': row['branch_id'],
            'photo_html': row.get('photo_html')
        }

        return jsonify({'status': 'success', 'data': data})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# DESIGNATIONS (from designation_mst - vownjm database)
# ══════════════════════════════════════════════════════════════════

@app.route('/designations', methods=['GET'])
def get_designations():
    """
    Get designations from designation_mst table.
    Query params:
      ?branch_id=29              → all designations for that branch
      ?branch_id=29&sub_dept_id=1 → designations for that branch + department
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        sub_dept_id = request.args.get('sub_dept_id', type=int)

        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        if sub_dept_id:
            # Filter by sub_dept + branch
            query = """
                SELECT DISTINCT dm.designation_id AS id, dm.desig AS name
                FROM designation_mst dm
                JOIN sub_dept_mst s ON dm.dept_id = s.dept_id
                WHERE s.sub_dept_id = %s AND dm.branch_id = %s AND dm.active = 1
                ORDER BY dm.desig
            """
            cursor.execute(query, (sub_dept_id, branch_id))
        else:
            # All designations for branch
            query = """
                SELECT designation_id AS id, desig AS name
                FROM designation_mst
                WHERE branch_id = %s AND active = 1
                ORDER BY desig
            """
            cursor.execute(query, (branch_id,))

        data = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'data': data, 'total': len(data)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# MACHINES
# ══════════════════════════════════════════════════════════════════

@app.route('/machines', methods=['GET'])
def get_machines():
    """
    Get machines by designation (occupation) ID
    Query params:
      ?designation_id=<id>  → required
    Returns machine details including mech_code and machine_name
    """
    try:
        designation_id = request.args.get('designation_id', type=int)

        if not designation_id:
            return jsonify({'status': 'error', 'message': 'designation_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Fetch machines linked to designation/occupation
        query = """
            SELECT 
                mm.machine_id,
                mm.machine_name,
                mm.mech_code,
                mm.mech_shr_code,
                mm.line_no,
                mm.machine_type_id,
                mm.dept_id,
                mm.active
            FROM sjm.machine_mst mm
            LEFT JOIN sjm.mech_occu_link mol ON mm.machine_id = mol.mech_id
            WHERE mol.occu_id = %s AND mm.active = 1
            ORDER BY mm.mech_code, mm.machine_name
        """
        cursor.execute(query, (designation_id,))
        raw_machines = cursor.fetchall()
        
        # Format response to match frontend expectations
        machines = []
        for m in raw_machines:
            # Build display name: combine mech_code with machine_name if both exist
            mech_code = m['mech_code'] or ''
            machine_name = m['machine_name'] or ''
            
            # Create display name: "mech_code machine_name" or just one if the other is empty
            if mech_code and machine_name:
                display_name = f"{mech_code} {machine_name}"
            elif mech_code:
                display_name = mech_code
            elif machine_name:
                display_name = machine_name
            else:
                display_name = f"Machine {m['machine_id']}"
            
            machines.append({
                'id': m['machine_id'],
                'name': display_name,  # Send the combined display name
                'mech_code': mech_code,
                'machine_no': m['mech_shr_code'] or ''
            })

        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'data': machines, 'total': len(machines)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# EMPLOYEES
# ══════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════
# ON BOARDING - Face Registration
# ══════════════════════════════════════════════════════════════════

@app.route('/onboarding/employee/<emp_code>', methods=['GET'])
def onboarding_get_employee(emp_code):
    """
    Lookup employee by emp_code.
    Returns employee details + current face count (max 3 allowed).
    emp_code must exist in hrms_ed_official_details.
    """
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Lookup employee by emp_code in official_details, join with personal_details
        cursor.execute("""
            SELECT p.eb_id,
                   o.emp_code,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
                   o.sub_dept_id,
                   o.designation_id,
                   o.branch_id,
                   s.sub_dept_desc AS department_name,
                   d.desig AS designation_name
            FROM hrms_ed_official_details o
            INNER JOIN hrms_ed_personal_details p ON o.eb_id = p.eb_id
            LEFT JOIN sub_dept_mst s ON o.sub_dept_id = s.sub_dept_id
            LEFT JOIN designation_mst d ON o.designation_id = d.designation_id
            WHERE o.emp_code = %s AND p.active = 1
            LIMIT 1
        """, (emp_code,))
        employee = cursor.fetchone()

        if not employee:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': f'Employee with emp_code {emp_code} not found or not in official records'}), 404

        eb_id = employee['eb_id']

        # Count existing registered faces
        cursor.execute("SELECT COUNT(*) AS cnt FROM employee_face_mst WHERE eb_id = %s AND active = 1", (eb_id,))
        face_count = cursor.fetchone()['cnt']

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'eb_id': eb_id,
            'emp_code': employee['emp_code'],
            'name': employee['name'].strip(),
            'department_name': employee['department_name'] or '',
            'designation_name': employee['designation_name'] or '',
            'branch_id': employee['branch_id'],
            'face_count': face_count,
            'can_register': face_count < 3
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/onboarding/register-face', methods=['POST'])
def onboarding_register_face():
    """
    Register a face for an employee.
    Body: { emp_code, face_image (base64) }
    Max 3 faces allowed per employee.
    emp_code must exist in hrms_ed_official_details.
    """
    try:
        data = request.get_json()
        emp_code = data.get('emp_code')
        face_image_b64 = data.get('face_image')

        if not emp_code:
            return jsonify({'status': 'error', 'message': 'emp_code is required'}), 400
        if not face_image_b64:
            return jsonify({'status': 'error', 'message': 'face_image is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Verify employee exists - lookup by emp_code in official_details
        cursor.execute("""
            SELECT p.eb_id, o.emp_code,
                   CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name
            FROM hrms_ed_official_details o
            INNER JOIN hrms_ed_personal_details p ON o.eb_id = p.eb_id
            WHERE o.emp_code = %s AND p.active = 1
            LIMIT 1
        """, (emp_code,))
        employee = cursor.fetchone()

        if not employee:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': f'Employee with emp_code {emp_code} not found or not in official records'}), 404

        eb_id = employee['eb_id']

        # Check face count — max 3
        cursor.execute("SELECT COUNT(*) AS cnt FROM employee_face_mst WHERE eb_id = %s AND active = 1", (eb_id,))
        face_count = cursor.fetchone()['cnt']

        if face_count >= 3:
            cursor.close()
            db.close()
            return jsonify({
                'status': 'error',
                'message': f'Maximum 3 faces already registered for {employee["name"].strip()}. Cannot add more.'
            }), 400

        # Generate face embedding
        image_bytes = base64.b64decode(face_image_b64)
        embedding = generate_face_embedding(image_bytes)
        face_embedding_json = json.dumps(embedding) if embedding is not None else None

        if not face_embedding_json:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'No face detected in the image. Please try again.'}), 400

        # Insert new face record
        cursor.execute("""
            INSERT INTO employee_face_mst (eb_id, face_embedding, active, photo_html, updated_by, updated_date_time)
            VALUES (%s, %s, 1, %s, 0, NOW())
        """, (eb_id, face_embedding_json, face_image_b64))
        db.commit()

        new_face_count = face_count + 1
        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'message': f'Face registered successfully for {employee["name"].strip()} ({emp_code}) - {new_face_count}/3',
            'face_count': new_face_count,
            'can_register': new_face_count < 3
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# LEAVE TYPES
# ══════════════════════════════════════════════════════════════════

@app.route('/leave-types', methods=['GET'])
def get_leave_types():
    """Return all leave types from leave_types table."""
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, leave_type_name FROM leave_types ORDER BY leave_type_name")
            rows = cursor.fetchall()
        except Exception:
            # Table may not exist yet – return sensible defaults
            rows = []
        cursor.close()
        db.close()
        if not rows:
            rows = [
                {'id': 1, 'leave_type_name': 'Casual Leave'},
                {'id': 2, 'leave_type_name': 'Sick Leave'},
                {'id': 3, 'leave_type_name': 'Earned Leave'},
                {'id': 4, 'leave_type_name': 'Maternity Leave'},
                {'id': 5, 'leave_type_name': 'Paternity Leave'},
                {'id': 6, 'leave_type_name': 'Loss of Pay'},
                {'id': 7, 'leave_type_name': 'Compensatory Off'},
                {'id': 8, 'leave_type_name': 'Other'},
            ]
        return jsonify({'status': 'success', 'leave_types': rows})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# LEAVE TRANSACTIONS
# ══════════════════════════════════════════════════════════════════

@app.route('/leave-transactions', methods=['GET'])
def get_leave_transactions():
    """
    List leave transactions.
    Params: branch_id, co_id, from_date, to_date, emp_code, status
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        co_id     = request.args.get('co_id',     type=int)
        from_date = request.args.get('from_date')
        to_date   = request.args.get('to_date')
        emp_code  = request.args.get('emp_code', '').strip() or None
        status    = request.args.get('status',   '').strip() or None

        db     = get_db()
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT lt.id, lt.eb_id, lt.leave_type,
                   DATE_FORMAT(lt.from_date, '%%Y-%%m-%%d') AS `from`,
                   DATE_FORMAT(lt.to_date,   '%%Y-%%m-%%d') AS `to`,
                   lt.no_of_days, lt.reason, lt.status,
                   lt.branch_id, lt.co_id,
                   DATE_FORMAT(lt.created_at, '%%Y-%%m-%%d %%H:%%i') AS created_at,
                   COALESCE(o.emp_code, '') AS emp_code,
                   TRIM(CONCAT(COALESCE(p.first_name,''), ' ',
                               COALESCE(p.middle_name,''), ' ',
                               COALESCE(p.last_name,'')))  AS emp_name
            FROM leave_transactions lt
            LEFT JOIN hrms_ed_official_details o ON lt.eb_id = o.eb_id
            LEFT JOIN hrms_ed_personal_details p ON lt.eb_id = p.eb_id
            WHERE 1=1
        """
        params = []

        if branch_id:
            sql += " AND lt.branch_id = %s"; params.append(branch_id)
        if co_id:
            sql += " AND lt.co_id = %s";     params.append(co_id)
        if from_date:
            sql += " AND lt.from_date >= %s"; params.append(from_date)
        if to_date:
            sql += " AND lt.to_date <= %s";   params.append(to_date)
        if emp_code:
            sql += " AND o.emp_code = %s";    params.append(emp_code)
        if status:
            sql += " AND lt.status = %s";     params.append(status)

        sql += " ORDER BY lt.from_date DESC, lt.id DESC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        # Fetch detail rows for each transaction
        transactions = []
        for row in rows:
            cursor.execute("""
                SELECT id, tran_id,
                       DATE_FORMAT(leave_date, '%%Y-%%m-%%d') AS leave_date,
                       day_type, remarks
                FROM leave_tran_details
                WHERE tran_id = %s ORDER BY leave_date
            """, (row['id'],))
            details = cursor.fetchall()
            row['details'] = details
            transactions.append(row)

        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'transactions': transactions})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/leave-transactions', methods=['POST'])
def save_leave_transaction():
    """Create a new leave transaction with detail rows."""
    try:
        data           = request.json or {}
        eb_id          = data.get('eb_id')
        leave_type     = data.get('leave_type', '')
        from_date      = data.get('from_date')
        to_date        = data.get('to_date')
        no_of_days     = data.get('no_of_days', 0)
        reason         = data.get('reason', '')
        status         = data.get('status', 'Pending')
        branch_id      = data.get('branch_id')
        co_id          = data.get('co_id')
        details        = data.get('details', [])

        if not eb_id or not from_date or not to_date:
            return jsonify({'status': 'error', 'message': 'eb_id, from_date, to_date are required'}), 400

        db     = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO leave_transactions
                (eb_id, leave_type, from_date, to_date, no_of_days, reason, status, branch_id, co_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (eb_id, leave_type, from_date, to_date, no_of_days, reason, status, branch_id, co_id))
        tran_id = cursor.lastrowid

        for d in details:
            cursor.execute("""
                INSERT INTO leave_tran_details (tran_id, leave_date, day_type, remarks)
                VALUES (%s, %s, %s, %s)
            """, (tran_id, d.get('leave_date'), d.get('day_type', 'Full'), d.get('remarks', '')))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Leave saved successfully', 'id': tran_id})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/leave-transactions/<int:id>', methods=['DELETE'])
def delete_leave_transaction(id):
    """Delete a leave transaction and its details."""
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM leave_tran_details WHERE tran_id = %s", (id,))
        cursor.execute("DELETE FROM leave_transactions WHERE id = %s", (id,))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Leave deleted successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# EMP-WISE ATTENDANCE REPORT
# ══════════════════════════════════════════════════════════════════

@app.route('/emp-wise-attendance', methods=['GET'])
def emp_wise_attendance():
    """
    Employee-wise attendance report.
    Params:
      from_date, to_date  - date range (yyyy-MM-dd)
      spell_id            - filter by spell
      dept_id             - filter by department (sub_dept_mst)
      designation_id      - filter by designation
      att_type            - R / O / C (Regular/OT/Cash), empty = all
      report_type         - date_wise | fn_wise | monthly
      branch_id           - filter by branch
    """
    try:
        from_date      = request.args.get('from_date')
        to_date        = request.args.get('to_date')
        spell_id       = request.args.get('spell_id',       type=int)
        dept_id        = request.args.get('dept_id',        type=int)
        designation_id = request.args.get('designation_id', type=int)
        att_type       = request.args.get('att_type', '').strip()
        report_type    = request.args.get('report_type', 'date_wise').strip()
        branch_id      = request.args.get('branch_id',      type=int)

        if not from_date or not to_date:
            return jsonify({'status': 'error', 'message': 'from_date and to_date are required'}), 400

        db     = get_db()
        cursor = db.cursor(dictionary=True)

        # ── Resolve spell name from spell_id ──────────────────────
        spell_name_filter = None
        if spell_id:
            cursor.execute("SELECT spell_name FROM spell_mst WHERE spell_id = %s", (spell_id,))
            row = cursor.fetchone()
            spell_name_filter = row['spell_name'] if row else None

        # ── Build column periods ──────────────────────────────────
        from datetime import date as date_cls, timedelta
        fd = datetime.strptime(from_date, '%Y-%m-%d').date()
        td = datetime.strptime(to_date,   '%Y-%m-%d').date()

        if report_type == 'monthly':
            periods = []
            cur_d = date_cls(fd.year, fd.month, 1)
            while cur_d <= td:
                next_month = date_cls(cur_d.year + (cur_d.month // 12),
                                      (cur_d.month % 12) + 1, 1) if cur_d.month < 12 \
                             else date_cls(cur_d.year + 1, 1, 1)
                periods.append({'label': cur_d.strftime('%b-%Y'),
                                 'from': cur_d.strftime('%Y-%m-%d'),
                                 'to': (next_month - timedelta(days=1)).strftime('%Y-%m-%d')})
                cur_d = next_month

        elif report_type == 'fn_wise':
            try:
                cursor.execute("""
                    SELECT fne_name,
                           DATE_FORMAT(from_date, '%%Y-%%m-%%d') AS `from`,
                           DATE_FORMAT(to_date,   '%%Y-%%m-%%d') AS `to`
                    FROM fne_master
                    WHERE to_date >= %s AND from_date <= %s
                    ORDER BY from_date
                """, (from_date, to_date))
                fne_rows = cursor.fetchall()
            except Exception:
                fne_rows = []
            if fne_rows:
                periods = [{'label': r['fne_name'], 'from': r['from'], 'to': r['to']} for r in fne_rows]
            else:
                # fallback: 15-day splits
                periods = []
                cur_d = fd
                while cur_d <= td:
                    end_d = min(cur_d + timedelta(days=14), td)
                    periods.append({'label': cur_d.strftime('%d-%b') + ' to ' + end_d.strftime('%d-%b'),
                                    'from': cur_d.strftime('%Y-%m-%d'), 'to': end_d.strftime('%Y-%m-%d')})
                    cur_d = end_d + timedelta(days=1)

        else:  # date_wise
            periods = []
            cur_d = fd
            while cur_d <= td:
                periods.append({'label': cur_d.strftime('%d-%b'),
                                 'from': cur_d.strftime('%Y-%m-%d'),
                                 'to':   cur_d.strftime('%Y-%m-%d')})
                cur_d += timedelta(days=1)

        # ── Fetch employees ───────────────────────────────────────
        emp_sql = """
            SELECT DISTINCT o.eb_id,
                   COALESCE(o.emp_code, '') AS emp_code,
                   TRIM(CONCAT(COALESCE(p.first_name,''), ' ',
                               COALESCE(p.middle_name,''), ' ',
                               COALESCE(p.last_name,''))) AS emp_name,
                   COALESCE(s.sub_dept_desc, '') AS dept_name,
                   COALESCE(d.desig, '')          AS desig_name
            FROM hrms_ed_official_details o
            LEFT JOIN hrms_ed_personal_details p ON o.eb_id = p.eb_id
            LEFT JOIN sub_dept_mst s        ON o.sub_dept_id  = s.sub_dept_id
            LEFT JOIN designation_mst d     ON o.designation_id = d.designation_id
            WHERE (o.active IS NULL OR o.active != 0)
        """
        emp_params = []
        if branch_id:
            emp_sql += " AND o.branch_id = %s"
            emp_params.append(branch_id)
        if dept_id:
            emp_sql += " AND o.sub_dept_id = %s"
            emp_params.append(dept_id)
        if designation_id:
            emp_sql += " AND o.designation_id = %s"
            emp_params.append(designation_id)
        emp_sql += " ORDER BY o.emp_code"

        cursor.execute(emp_sql, tuple(emp_params))
        employees = cursor.fetchall()

        # ── Fetch attendance (SUM working_hours per employee per date) ──
        att_sql = """
            SELECT da.eb_id,
                   DATE_FORMAT(da.attendance_date, '%%Y-%%m-%%d') AS att_date,
                   COUNT(*)                                        AS att_count,
                   SUM(COALESCE(da.working_hours, 0))             AS total_hours
            FROM daily_attendance da
            WHERE da.attendance_date BETWEEN %s AND %s
              AND (da.is_active IS NULL OR da.is_active = 1)
        """
        att_params = [from_date, to_date]
        if branch_id:
            att_sql += " AND da.branch_id = %s"
            att_params.append(branch_id)
        if spell_name_filter:
            att_sql += " AND da.spell = %s"
            att_params.append(spell_name_filter)
        if att_type:
            att_sql += " AND da.attendance_type = %s"
            att_params.append(att_type)
        if dept_id:
            att_sql += " AND da.worked_department_id = %s"
            att_params.append(dept_id)
        if designation_id:
            att_sql += " AND da.worked_designation_id = %s"
            att_params.append(designation_id)
        att_sql += " GROUP BY da.eb_id, da.attendance_date"

        cursor.execute(att_sql, tuple(att_params))
        att_rows = cursor.fetchall()
        cursor.close()
        db.close()

        # Build lookup: eb_id -> {date_str: (count, hours)}
        from collections import defaultdict
        att_map = defaultdict(dict)
        for r in att_rows:
            hrs   = float(r['total_hours'] or 0)
            cnt   = int(r['att_count'] or 0)
            att_map[r['eb_id']][r['att_date']] = (cnt, hrs)

        # ── Build response rows ───────────────────────────────────
        result_rows = []
        for emp in employees:
            eb_id    = emp['eb_id']
            emp_data = att_map.get(eb_id, {})

            attendance = {}
            total_hours = 0.0
            days_present = 0

            for period in periods:
                pf = datetime.strptime(period['from'], '%Y-%m-%d').date()
                pt = datetime.strptime(period['to'],   '%Y-%m-%d').date()
                period_count = 0
                period_hours = 0.0
                d = pf
                while d <= pt:
                    rec = emp_data.get(d.strftime('%Y-%m-%d'))
                    if rec:
                        period_count += rec[0]
                        period_hours += rec[1]
                    d += timedelta(days=1)

                if period_count > 0:
                    if period_hours > 0:
                        val = int(period_hours) if period_hours == int(period_hours) else round(period_hours, 1)
                    else:
                        val = 'P'
                    attendance[period['label']] = val
                    total_hours += period_hours
                    days_present += 1
                else:
                    attendance[period['label']] = ''

            total_absent = len(periods) - days_present

            result_rows.append({
                'emp_code':      emp['emp_code'],
                'emp_name':      emp['emp_name'],
                'dept':          emp['dept_name'],
                'designation':   emp['desig_name'],
                'attendance':    attendance,
                'total_hours':   round(total_hours, 1),
                'total_present': days_present,
                'total_absent':  total_absent,
            })

        # Only return employees who have at least 1 attendance record
        result_rows = [r for r in result_rows if r['total_present'] > 0]

        columns = [p['label'] for p in periods]
        return jsonify({
            'status':          'success',
            'report_type':     report_type,
            'from_date':       from_date,
            'to_date':         to_date,
            'columns':         columns,
            'total_employees': len(result_rows),
            'employees':       result_rows,
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500



# ══════════════════════════════════════════════════════════════════
# WINDING ENTRY 2 - QUALITY-WISE SHIFT-WISE REPORT
# ══════════════════════════════════════════════════════════════════

@app.route('/doff/winding-entry-2-quality-shift-report', methods=['GET'])
def get_winding_entry_2_quality_shift_report():
    """
    Get quality-wise shift-wise production report for Winding Entry 2
    Query params:
      ?date=2024-01-15  → required (filter by date)
      ?branch_id=1      → required
    Returns:
      - report: List of quality rows with shift A/B/C totals
      - grand_total: Overall totals for each shift
    """
    try:
        date_str = request.args.get('date')
        branch_id = request.args.get('branch_id', type=int)

        if not date_str:
            return jsonify({'status': 'error', 'message': 'date is required'}), 400
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Main query: Get quality-wise shift-wise totals
        # Assuming we have quality info in spinning_quality_mst and spell_mst for shifts
        # We'll group by quality and spell to get the breakdown
        query = """
            SELECT 
                COALESCE(q.quality_name, 'Unknown') AS quality_name,
                COALESCE(SUM(CASE WHEN s.spell_name LIKE '%A%' THEN we.net_weight ELSE 0 END), 0) AS shift_a,
                COALESCE(SUM(CASE WHEN s.spell_name LIKE '%B%' THEN we.net_weight ELSE 0 END), 0) AS shift_b,
                COALESCE(SUM(CASE WHEN s.spell_name LIKE '%C%' THEN we.net_weight ELSE 0 END), 0) AS shift_c,
                COALESCE(SUM(we.net_weight), 0) AS total
            FROM winding_entry_2 we
            LEFT JOIN spell_mst s ON we.spell_id = s.spell_id
            LEFT JOIN spinning_quality_mst q ON we.quality_id = q.quality_id
            WHERE we.winding_date = %s
              AND we.branch_id = %s
              AND (we.is_active IS NULL OR we.is_active = 1)
            GROUP BY q.quality_name
            ORDER BY q.quality_name
        """
        
        cursor.execute(query, (date_str, branch_id))
        report_rows = cursor.fetchall()

        # Calculate grand totals
        grand_total_a = sum(row['shift_a'] for row in report_rows)
        grand_total_b = sum(row['shift_b'] for row in report_rows)
        grand_total_c = sum(row['shift_c'] for row in report_rows)
        grand_total = sum(row['total'] for row in report_rows)

        cursor.close()
        db.close()

        return jsonify({
            'status': 'success',
            'message': 'Quality-wise shift-wise report generated',
            'report': report_rows,
            'grand_total': {
                'shift_a': grand_total_a,
                'shift_b': grand_total_b,
                'shift_c': grand_total_c,
                'total': grand_total
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# DRAWING METER ENTRY ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.route('/drawing/sheds', methods=['GET'])
def get_drawing_sheds():
    """Get unique shed types from tbl_drawing_mst"""
    try:
        branch_id = request.args.get('branch_id', type=int)
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        query = """
            SELECT DISTINCT shed_type
            FROM tbl_drawing_mst
            WHERE 1=1
        """
        params = []
        
        if branch_id:
            query += " AND branch_id = %s"
            params.append(branch_id)
        
        query += " ORDER BY shed_type"
        
        cursor.execute(query, params if params else None)
        sheds = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({
            'status': 'success',
            'sheds': [s['shed_type'] for s in sheds]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/drawing/machines', methods=['GET'])
def get_drawing_machines():
    """Get machines for a specific shed type"""
    try:
        shed_type = request.args.get('shed_type')
        branch_id = request.args.get('branch_id', type=int)
        
        if not shed_type:
            return jsonify({'status': 'error', 'message': 'shed_type required'}), 400
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        query = """
            SELECT mc_id, mc_short_name, cont_meter
            FROM tbl_drawing_mst
            WHERE shed_type = %s
        """
        params = [shed_type]
        
        if branch_id:
            query += " AND branch_id = %s"
            params.append(branch_id)
        
        query += " ORDER BY mc_short_name"
        
        cursor.execute(query, params)
        machines = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({
            'status': 'success',
            'machines': machines
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/drawing/opening-meter', methods=['GET'])
def get_drawing_opening_meter():
    """Get opening meter (previous closing meter) for a machine"""
    try:
        date_str = request.args.get('date')
        spell_id = request.args.get('spell_id', type=int)
        mc_id = request.args.get('mc_id', type=int)
        
        if not all([date_str, spell_id, mc_id]):
            return jsonify({'status': 'error', 'message': 'date, spell_id, mc_id required'}), 400
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Get the most recent closing meter for this machine before the current date+spell
        query = """
            SELECT closing_meter
            FROM tbl_daily_drawing
            WHERE mc_id = %s
              AND (date < %s OR (date = %s AND spell_id < %s))
            ORDER BY date DESC, spell_id DESC
            LIMIT 1
        """
        
        cursor.execute(query, (mc_id, date_str, date_str, spell_id))
        result = cursor.fetchone()
        
        cursor.close()
        db.close()
        
        opening_meter = result['closing_meter'] if result else 0.0
        
        return jsonify({
            'status': 'success',
            'opening_meter': opening_meter
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/drawing/entry', methods=['POST'])
def save_drawing_entry():
    """Save drawing meter entry"""
    try:
        data = request.get_json()
        
        date_str = data.get('date')
        spell_id = data.get('spell_id')
        shed_type = data.get('shed_type')
        mc_id = data.get('mc_id')
        opening_meter = data.get('opening_meter', 0.0)
        closing_meter = data.get('closing_meter', 0.0)
        hours = data.get('hours', 0.0)
        const_value = data.get('const_value', 1.0)  # Efficiency constant
        branch_id = data.get('branch_id')
        user_id = data.get('user_id', 0)
        
        if not all([date_str, spell_id, shed_type, mc_id]):
            return jsonify({'status': 'error', 'message': 'Required fields missing'}), 400
        
        # Calculate unit and efficiency
        unit = closing_meter - opening_meter
        if hours > 0 and const_value > 0:
            eff = round(((unit / hours * 8) / const_value * 100), 2)
        else:
            eff = 0.0
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if entry exists for this date+spell+mc
        cursor.execute("""
            SELECT id FROM tbl_daily_drawing
            WHERE date = %s AND spell_id = %s AND mc_id = %s
        """, (date_str, spell_id, mc_id))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing entry
            cursor.execute("""
                UPDATE tbl_daily_drawing
                SET shed_type = %s, opening_meter = %s, closing_meter = %s,
                    unit = %s, hours = %s, eff = %s, branch_id = %s,
                    user_id = %s, updated_at = NOW()
                WHERE id = %s
            """, (shed_type, opening_meter, closing_meter, unit, hours, eff,
                  branch_id, user_id, existing[0]))
            entry_id = existing[0]
        else:
            # Insert new entry
            cursor.execute("""
                INSERT INTO tbl_daily_drawing
                (date, spell_id, shed_type, mc_id, opening_meter, closing_meter,
                 unit, hours, eff, branch_id, user_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (date_str, spell_id, shed_type, mc_id, opening_meter, closing_meter,
                  unit, hours, eff, branch_id, user_id))
            entry_id = cursor.lastrowid
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Entry saved successfully',
            'id': entry_id,
            'unit': unit,
            'eff': eff
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/drawing/summary', methods=['GET'])
def get_drawing_summary():
    """Get drawing meter entry summary for date+spell"""
    try:
        date_str = request.args.get('date')
        spell_id = request.args.get('spell_id', type=int)
        branch_id = request.args.get('branch_id', type=int)
        
        if not all([date_str, spell_id]):
            return jsonify({'status': 'error', 'message': 'date and spell_id required'}), 400
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        query = """
            SELECT 
                d.mc_id,
                m.mc_short_name,
                d.unit,
                d.eff
            FROM tbl_daily_drawing d
            JOIN tbl_drawing_mst m ON d.mc_id = m.mc_id
            WHERE d.date = %s AND d.spell_id = %s
        """
        params = [date_str, spell_id]
        
        if branch_id:
            query += " AND d.branch_id = %s"
            params.append(branch_id)
        
        query += " ORDER BY m.mc_short_name"
        
        cursor.execute(query, params)
        summary = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({
            'status': 'success',
            'summary': summary
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

