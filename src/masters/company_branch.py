from flask import Blueprint, request, jsonify
from db import get_db
from src.masters import query as Q

company_branch_bp = Blueprint('company_branch', __name__)


@company_branch_bp.route('/masters/get_company', methods=['GET'])
def get_company():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        print("Executing query to fetch companies...",Q.GET_ALL_COMPANIES )
        cursor.execute(Q.GET_ALL_COMPANIES)
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        return jsonify({
            "status": "success",
            "total": len(rows),
            "companies": rows,
            "data": rows
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@company_branch_bp.route('/masters/get_branch', methods=['GET'])
def get_branch():
    try:
        raw_company_id = request.args.get('company_id') or request.args.get('co_id')
        if not raw_company_id:
            return jsonify({
                "status": "error",
                "message": "company_id (or co_id) is required"
            }), 400

        try:
            company_id = int(raw_company_id)
            if company_id <= 0:
                raise ValueError
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "company_id must be a positive integer"
            }), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(Q.GET_BRANCHES_BY_COMPANY, (company_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        return jsonify({
            "status": "success",
            "total": len(rows),
            "branches": rows,
            "data": rows
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

