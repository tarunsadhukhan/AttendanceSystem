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
        return jsonify({'status': 'success', 'data': data, 'total': len(data)})
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
                       sm.starting_time AS start_time, sm.end_time
                FROM spell_mst sm
                JOIN shift_mst sh ON sm.shift_id = sh.shift_id
                WHERE sh.branch_id = %s
                ORDER BY sm.spell_name
            """, (branch_id,))
        else:
            cursor.execute("""
                SELECT spell_id AS id, spell_name AS name,
                       starting_time AS start_time, end_time
                FROM spell_mst ORDER BY spell_name
            """)

        data = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'data': data, 'total': len(data)})
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
            SELECT id, emp_code, name, photo_html,
                   department_id, designation_id, shift_id
            FROM employees
            WHERE is_active = 1
              AND (name LIKE %s OR emp_code LIKE %s)
            ORDER BY name
            LIMIT 20
        """, (search_pattern, search_pattern))
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
            }), 404

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
        cursor.execute(manual_query, tuple(manual_params))
        present_manual = cursor.fetchone()['cnt']

        # Absent = total employees - present
        total_absent = max(0, total_employees - total_present)

        # Department-wise statistics (filtered by branch)
        # Using better query to get department data with present count in one go
        dept_stats_query = """
            SELECT 
                sdm.sub_dept_id AS department_id,
                sdm.sub_dept_desc AS department_name,
                COUNT(DISTINCT o.emp_id) AS total_employees,
                COALESCE(SUM(CASE WHEN da.attendance_date = %s THEN 1 ELSE 0 END), 0) AS present
            FROM sub_dept_mst sdm
            LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
            LEFT JOIN hrms_ed_official_details o ON sdm.sub_dept_id = o.sub_dept_id
            LEFT JOIN daily_attendance da ON da.eb_id = o.eb_id 
                AND da.worked_department_id = sdm.sub_dept_id 
                AND da.attendance_date = %s
        """
        dept_stats_params = [stat_date, stat_date]
        
        if branch_id:
            dept_stats_query += " WHERE dm.branch_id = %s"
            dept_stats_params.append(branch_id)
        elif co_id:
            dept_stats_query += " WHERE dm.co_id = %s"
            dept_stats_params.append(co_id)
        
        dept_stats_query += " GROUP BY sdm.sub_dept_id, sdm.sub_dept_desc ORDER BY sdm.sub_dept_desc"

        cursor.execute(dept_stats_query, tuple(dept_stats_params))
        dept_stats = cursor.fetchall()

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
            WHERE da.attendance_date = %s AND da.is_active = 1
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
                WHERE dea.daily_atten_id = %s AND dea.is_active = 1
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
            WHERE da.daily_atten_id = %s AND da.is_active = 1
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
# RUN SERVER
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("🚀 Starting MyHrms Flask Server...")
    print(f"📊 Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    init_db()  # Run database migrations on startup
    
    port = int(os.getenv('FLASK_PORT', 5051))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"✅ Server ready at http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

