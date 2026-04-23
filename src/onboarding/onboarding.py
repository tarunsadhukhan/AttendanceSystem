"""
OnBoarding Blueprint - Face Registration for Employees
Allows registering up to 3 face photos per employee (by emp_code)
"""

import json
import base64

try:
    import face_recognition
except ImportError:
    face_recognition = None

from flask import Blueprint, request, jsonify
from db import get_db
from src.onboarding import query as Q

onboarding_bp = Blueprint('onboarding', __name__)


def _generate_face_embedding(image_bytes):
    """
    Generate 128-d face embedding from image bytes.
    Returns embedding list or None if no face detected.
    """
    if face_recognition is None:
        return None
    
    try:
        import numpy as np
        from PIL import Image
        import io
        
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(image_np)
        
        if len(face_encodings) == 0:
            return None
        
        # Return first face encoding as list
        return face_encodings[0].tolist()
    except Exception as e:
        print(f"Error generating face embedding: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# GET Employee by emp_code
# ══════════════════════════════════════════════════════════════════

@onboarding_bp.route('/onboarding/employee/<emp_code>', methods=['GET'])
def get_employee(emp_code):
    """
    Lookup employee by emp_code.
    Returns employee details + current face count (max 3 allowed).
    emp_code must exist in hrms_ed_official_details.
    """
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Get employee by emp_code
        cursor.execute(Q.GET_EMPLOYEE_BY_EMP_CODE, (emp_code,))
        employee = cursor.fetchone()
        
        if not employee:
            cursor.close()
            db.close()
            return jsonify({
                'status': 'error',
                'message': f'Employee with emp_code {emp_code} not found or not in official records'
            }), 404
        
        eb_id = employee['eb_id']
        
        # Count existing registered faces
        cursor.execute(Q.GET_FACE_COUNT, (eb_id,))
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


# ══════════════════════════════════════════════════════════════════
# POST Register Face
# ══════════════════════════════════════════════════════════════════

@onboarding_bp.route('/onboarding/register-face', methods=['POST'])
def register_face():
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
        cursor.execute(Q.GET_EMPLOYEE_BY_EMP_CODE, (emp_code,))
        employee = cursor.fetchone()
        
        if not employee:
            cursor.close()
            db.close()
            return jsonify({
                'status': 'error',
                'message': f'Employee with emp_code {emp_code} not found or not in official records'
            }), 404
        
        eb_id = employee['eb_id']
        
        # Check face count — max 3
        cursor.execute(Q.GET_FACE_COUNT, (eb_id,))
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
        embedding = _generate_face_embedding(image_bytes)
        face_embedding_json = json.dumps(embedding) if embedding is not None else None
        
        if not face_embedding_json:
            cursor.close()
            db.close()
            return jsonify({
                'status': 'error',
                'message': 'No face detected in the image. Please try again.'
            }), 400
        
        # Insert new face record
        cursor.execute(Q.INSERT_FACE, (eb_id, face_embedding_json, face_image_b64))
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

