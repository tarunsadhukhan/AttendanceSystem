import bcrypt
import mysql.connector
from flask import Blueprint, request, jsonify
from db import get_auth_db
from src.auth import query as Q
from src.schemas.user import SignupSchema, LoginSchema

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        ok, errors = SignupSchema.validate(data)
        if not ok:
            return jsonify({"status": "error", "message": errors[0]}), 400

        email_id  = data.get('email_id', '').strip()
        name      = data.get('name', '').strip()
        password  = data.get('password', '')

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db        = get_auth_db()
        cursor    = db.cursor()
        cursor.execute(Q.INSERT_USER, (email_id, name, hashed_pw))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"status": "success",
                        "message": f"User '{email_id}' created!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error",
                        "message": "Email already exists!"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        ok, errors = LoginSchema.validate(data)
        if not ok:
            return jsonify({"status": "error", "message": errors[0]}), 400

        # accept email_id or username (legacy Android client)
        email_id = (data.get('email_id') or data.get('username', '')).strip()
        password = data.get('password', '')

        db     = get_auth_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(Q.GET_USER_BY_EMAIL, (email_id,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if not user or not bcrypt.checkpw(password.encode(), user['password'].encode()):
            return jsonify({"status": "error",
                            "message": "Invalid email or password!"}), 401

        return jsonify({
            "status":  "success",
            "message": "Login successful!",
            "user": {
                "user_id":  user['user_id'],
                "email_id": user['email_id'],
                "name":     user['name'],
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
