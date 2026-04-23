import json
import re
try:
    import face_recognition
except ImportError:
    face_recognition = None

import numpy as np
import mysql.connector
from flask import Blueprint, request, jsonify
from db import get_db
from src.utils import decode_image
from src.employees import query as Q
from src.schemas.employee import RegisterEmployeeSchema, UpdateFaceSchema

employees_bp = Blueprint('employees', __name__)


def _require_face_recognition():
    if face_recognition is None:
        return jsonify({
            "status": "error",
            "message": "face_recognition dependency is not installed on server"
        }), 503
    return None


# ── GET all employees ────────────────────────────────────────
@employees_bp.route('/employees', methods=['GET'])
def get_employees():
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(Q.GET_ALL_EMPLOYEES)
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        for r in rows:
            r['photo_base64'] = None
            if r.get('photo_html'):
                match = re.search(r'base64,([^"]+)', r['photo_html'])
                if match:
                    r['photo_base64'] = match.group(1)
            r.pop('photo_html', None)

        return jsonify({"status": "success", "total": len(rows), "data": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── GET employee by emp_code ─────────────────────────────────
@employees_bp.route('/employee/<emp_code>', methods=['GET'])
def get_employee_by_code(emp_code):
    try:
        branch_id = request.args.get('branch_id')
        if not branch_id:
            return jsonify({"status": "error", "message": "branch_id is required"}), 400

        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(Q.GET_EMPLOYEE_BY_CODE, (emp_code, branch_id))
        employee = cursor.fetchone()
        cursor.close()
        db.close()

        if not employee:
            return jsonify({"status": "error",
                            "message": f"Employee code '{emp_code}' not found!"}), 404

        return jsonify({
            "status":           "success",
            "eb_id":            employee['eb_id'],
            "emp_code":         employee['emp_code'],
            "emp_name":         employee['name'].strip(),
            "department":       employee['department_name'] or '',
            "designation":      employee['designation_name'] or '',
            "branch_id":        employee['branch_id'],
            "message":          f"Employee found: {employee['name'].strip()}"
        })
    except Exception as e:
        print(f"❌ Employee lookup error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Register employee ────────────────────────────────────────
@employees_bp.route('/register', methods=['POST'])
def register():
    try:
        missing_dep = _require_face_recognition()
        if missing_dep:
            return missing_dep
        data = request.json
        ok, errors = RegisterEmployeeSchema.validate(data)
        if not ok:
            return jsonify({"status": "error", "message": errors[0]}), 400

        print(f"📥 Register POST data: {  {k: (v[:50] + '...') if k == 'image' and isinstance(v, str) and len(v) > 50 else v for k, v in data.items()}  }")

        img_rgb   = decode_image(data['image'])
        encodings = face_recognition.face_encodings(img_rgb)
        print(f"🔍 Detected {len(encodings)} face(s) for {data['name']}")

        if not encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        embedding = encodings[0].tolist()
        db        = get_db()
        cursor    = db.cursor()

        dept_id  = data.get('department_id')
        desig_id = data.get('designation_id')
        shift_id = data.get('shift_id')

        if not dept_id and data.get('department'):
            cursor.execute(Q.GET_DEPT_ID_BY_NAME, (data['department'],))
            row = cursor.fetchone()
            dept_id = row[0] if row else None

        if not desig_id and data.get('designation'):
            cursor.execute(Q.GET_DESIG_ID_BY_NAME, (data['designation'],))
            row = cursor.fetchone()
            desig_id = row[0] if row else None

        if not shift_id and data.get('shift'):
            cursor.execute(Q.GET_SHIFT_ID_BY_NAME, (data['shift'],))
            row = cursor.fetchone()
            shift_id = row[0] if row else None

        print(f"Registering {data['name']} with emp_code {data['emp_code']} "
              f"dept={dept_id} desig={desig_id} shift={shift_id}")

        photo_html = None
        try:
            photo_html = f'<img src="data:image/jpeg;base64,{data["image"]}" />'
            print(f"📸 Photo stored as HTML ({len(photo_html)} chars)")
        except Exception as pe:
            print(f"⚠️ Photo HTML build failed: {pe}")

        cursor.execute(Q.INSERT_EMPLOYEE,
                       (data['emp_code'], data['name'], dept_id, desig_id, shift_id,
                        json.dumps(embedding), photo_html))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"status": "success",
                        "message": f"{data['name']} registered!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Employee code already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Update employee face ─────────────────────────────────────
@employees_bp.route('/register/<emp_code>', methods=['PUT'])
def update_face(emp_code):
    try:
        missing_dep = _require_face_recognition()
        if missing_dep:
            return missing_dep
        data = request.json
        ok, errors = UpdateFaceSchema.validate(data)
        if not ok:
            return jsonify({"status": "error", "message": errors[0]}), 400

        img_rgb   = decode_image(data['image'])
        encodings = face_recognition.face_encodings(img_rgb)

        if not encodings:
            return jsonify({"status": "error",
                            "message": "No face detected!"}), 400

        embedding = encodings[0].tolist()
        db        = get_db()
        cursor    = db.cursor()
        cursor.execute(Q.UPDATE_EMPLOYEE_FACE, (json.dumps(embedding), emp_code))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Employee not found!"}), 404

        cursor.close()
        db.close()
        return jsonify({"status": "success",
                        "message": f"Face updated for emp_code {emp_code}!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Update employee details ──────────────────────────────────
@employees_bp.route('/employees/<int:emp_id>', methods=['PUT'])
def update_employee(emp_id):
    try:
        data   = request.json
        db     = get_db()
        cursor = db.cursor()

        fields = []
        values = []

        if 'name' in data:
            fields.append("name = %s"); values.append(data['name'])
        if 'emp_code' in data:
            fields.append("emp_code = %s"); values.append(data['emp_code'])
        if 'department_id' in data:
            fields.append("department_id = %s"); values.append(data['department_id'])
        if 'designation_id' in data:
            fields.append("designation_id = %s"); values.append(data['designation_id'])
        if 'shift_id' in data:
            fields.append("shift_id = %s"); values.append(data['shift_id'])

        if 'face_image' in data and data['face_image']:
            missing_dep = _require_face_recognition()
            if missing_dep:
                return missing_dep
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
        return jsonify({"status": "success", "message": "Employee updated!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Employee code already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Delete (soft) employee ───────────────────────────────────
@employees_bp.route('/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute(Q.SOFT_DELETE_EMPLOYEE, (emp_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error",
                            "message": "Employee not found!"}), 404

        cursor.close()
        db.close()
        return jsonify({"status": "success", "message": "Employee deleted!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
