"""
Jute Received module — endpoints.
Uses the project standard: mysql.connector via src.database.get_db.

Routes (mounted under /jute-received):
    GET    /jute-received/qualities      Jute qualities (jute_quality_mst, by branch)
    POST   /jute-received/entry          Save a Jute Received row
    PUT    /jute-received/entry/<id>     Update a Jute Received row
    GET    /jute-received/entry          List rows for date+branch
    DELETE /jute-received/entry/<id>     Delete a row
"""
from datetime import datetime
from flask import request, jsonify
from . import jute_received_bp
from src.database import get_db


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_table():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tbl_jute_received (
                tbl_jute_rcv_id     INT(11) NOT NULL AUTO_INCREMENT,
                recv_date           DATE DEFAULT NULL,
                quality_id          INT(11) DEFAULT NULL,
                no_of_bales         INT(11) DEFAULT NULL,
                weight              INT(11) DEFAULT NULL,
                branch_id           INT(11) DEFAULT NULL,
                updated_by          INT(11) DEFAULT NULL,
                updated_date_time   DATE DEFAULT NULL,
                PRIMARY KEY (tbl_jute_rcv_id),
                INDEX idx_jute_recv_date_branch (recv_date, branch_id)
            )
        """)
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"⚠️  tbl_jute_received create error (non-fatal): {e}")


def _to_int(val):
    if val is None or val == '':
        return None
    try:
        return int(round(float(val)))
    except Exception:
        return None


# ─── Qualities ────────────────────────────────────────────────────────────────

@jute_received_bp.route('/qualities', methods=['GET'])
def get_jute_received_qualities():
    """
    Jute qualities for Jute Received Entry.
    Source: jute_quality_mst — shr_name shown as button label, filtered by branch.
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        sql="""
                        SELECT jute_qlty_id AS quality_id,
                   COALESCE(shr_name, jute_quality) AS shr_name,
                   jute_quality AS quality_name
            FROM jute_quality_mst
            WHERE branch_id = %s
            ORDER BY shr_name, jute_quality
        """
        cursor.execute(sql, (branch_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'qualities': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Save ─────────────────────────────────────────────────────────────────────

@jute_received_bp.route('/entry', methods=['POST'])
def save_jute_received_entry():
    """
    Save a Jute Received row.
    Body JSON: { date, quality_id, no_of_bales, weight, branch_id, user_id }
    """
    try:
        _ensure_table()
        data = request.get_json() or {}
        recv_date   = data.get('date')
        quality_id  = data.get('quality_id')
        no_of_bales = _to_int(data.get('no_of_bales'))
        weight      = _to_int(data.get('weight'))
        branch_id   = data.get('branch_id')
        user_id     = data.get('user_id')

        if not all([recv_date, quality_id, branch_id]):
            return jsonify({'status': 'error',
                            'message': 'date, quality_id, branch_id are required'}), 400

        if (no_of_bales is None or no_of_bales <= 0) and (weight is None or weight <= 0):
            return jsonify({'status': 'error',
                            'message': 'Enter no_of_bales and/or weight'}), 400

        now = datetime.now().strftime('%Y-%m-%d')
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO tbl_jute_received
                (recv_date, quality_id, no_of_bales, weight, branch_id,
                 updated_by, updated_date_time)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (recv_date, quality_id, no_of_bales, weight, branch_id, user_id, now))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Update ───────────────────────────────────────────────────────────────────

@jute_received_bp.route('/entry/<int:entry_id>', methods=['PUT'])
def update_jute_received_entry(entry_id):
    """
    Update an existing Jute Received row.
    Body JSON: { date, quality_id, no_of_bales, weight, branch_id, user_id }
    """
    try:
        data = request.get_json() or {}
        recv_date   = data.get('date')
        quality_id  = data.get('quality_id')
        no_of_bales = _to_int(data.get('no_of_bales'))
        weight      = _to_int(data.get('weight'))
        branch_id   = data.get('branch_id')
        user_id     = data.get('user_id')

        if not all([recv_date, quality_id, branch_id]):
            return jsonify({'status': 'error',
                            'message': 'date, quality_id, branch_id are required'}), 400

        if (no_of_bales is None or no_of_bales <= 0) and (weight is None or weight <= 0):
            return jsonify({'status': 'error',
                            'message': 'Enter no_of_bales and/or weight'}), 400

        now = datetime.now().strftime('%Y-%m-%d')
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE tbl_jute_received
               SET recv_date         = %s,
                   quality_id        = %s,
                   no_of_bales       = %s,
                   weight            = %s,
                   branch_id         = %s,
                   updated_by        = %s,
                   updated_date_time = %s
             WHERE tbl_jute_rcv_id   = %s
        """, (recv_date, quality_id, no_of_bales, weight, branch_id, user_id, now, entry_id))
        affected = cursor.rowcount
        db.commit()
        cursor.close()
        db.close()

        if affected == 0:
            return jsonify({'status': 'error', 'message': 'Entry not found'}), 404
        return jsonify({'status': 'success', 'message': 'Updated', 'id': entry_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── List ─────────────────────────────────────────────────────────────────────

@jute_received_bp.route('/entry', methods=['GET'])
def list_jute_received_entries():
    """
    List jute received rows for a date and branch.
    Query: ?date=YYYY-MM-DD&branch_id=<>
    """
    try:
        _ensure_table()
        recv_date = request.args.get('date')
        branch_id = request.args.get('branch_id', type=int)
        if not all([recv_date, branch_id]):
            return jsonify({'status': 'error',
                            'message': 'date and branch_id are required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT j.tbl_jute_rcv_id                          AS id,
                   j.recv_date,
                   j.quality_id,
                   COALESCE(jq.shr_name, jq.jute_quality, '') AS quality,
                   j.no_of_bales,
                   j.weight
            FROM tbl_jute_received j
            LEFT JOIN jute_quality_mst jq ON j.quality_id = jq.jute_qlty_id
            WHERE j.recv_date = %s
              AND j.branch_id = %s
            ORDER BY j.tbl_jute_rcv_id DESC
        """, (recv_date, branch_id))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Delete ───────────────────────────────────────────────────────────────────

@jute_received_bp.route('/entry/<int:entry_id>', methods=['DELETE'])
def delete_jute_received_entry(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM tbl_jute_received WHERE tbl_jute_rcv_id = %s", (entry_id,))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
