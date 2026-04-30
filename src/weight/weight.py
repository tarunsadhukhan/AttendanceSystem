"""Weight Entry endpoints.

Auto-created table: weight_tran
  id, tran_date, branch_id, spell_id, emp_code, emp_name,
  gross_weight, tare_weight, net_weight, weight_type, created_by, created_at
"""
import traceback
from flask import Blueprint, request, jsonify
from db import get_db

weight_bp = Blueprint('weight', __name__)


def _ensure_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weight_tran (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            tran_date    DATE NOT NULL,
            branch_id    INT NOT NULL,
            spell_id     INT DEFAULT NULL,
            emp_code     VARCHAR(50)  DEFAULT NULL,
            emp_name     VARCHAR(200) DEFAULT NULL,
            gross_weight DECIMAL(10,3) DEFAULT 0,
            tare_weight  DECIMAL(10,3) DEFAULT 0,
            net_weight   DECIMAL(10,3) DEFAULT 0,
            weight_type  CHAR(1)       DEFAULT 'M',
            created_by   INT           DEFAULT 0,
            created_at   DATETIME      DEFAULT CURRENT_TIMESTAMP
        )
    """)


# ── GET /weight-transactions ──────────────────────────────────────────
@weight_bp.route('/weight-transactions', methods=['GET'])
def get_weight_transactions():
    try:
        branch_id  = request.args.get('branch_id', type=int)
        tran_date  = request.args.get('date')

        db  = get_db()
        cur = db.cursor(dictionary=True)
        _ensure_table(cur)
        db.commit()

        conditions, params = [], []
        if branch_id:
            conditions.append("wt.branch_id = %s")
            params.append(branch_id)
        if tran_date:
            conditions.append("wt.tran_date = %s")
            params.append(tran_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT wt.id, wt.tran_date, wt.branch_id,
                   wt.spell_id, s.spell_name,
                   wt.emp_code, wt.emp_name,
                   wt.gross_weight, wt.tare_weight, wt.net_weight,
                   wt.weight_type, wt.created_at
            FROM weight_tran wt
            LEFT JOIN spell_mst s ON s.spell_id = wt.spell_id
            {where}
            ORDER BY wt.id DESC
        """, params)

        rows = cur.fetchall()
        for r in rows:
            for k, v in list(r.items()):
                if hasattr(v, 'strftime'):
                    r[k] = v.strftime('%Y-%m-%d') if 'date' in k else str(v)
        cur.close(); db.close()
        return jsonify({'status': 'success', 'transactions': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── POST /weight-transactions ─────────────────────────────────────────
@weight_bp.route('/weight-transactions', methods=['POST'])
def save_weight_transaction():
    try:
        data         = request.get_json(force=True) or {}
        branch_id    = data.get('branch_id')
        tran_date    = data.get('tran_date')
        spell_id     = data.get('spell_id')
        emp_code     = data.get('emp_code')
        emp_name     = data.get('emp_name')
        gross_weight = data.get('gross_weight', 0)
        tare_weight  = data.get('tare_weight',  0)
        net_weight   = data.get('net_weight',   0)
        weight_type  = 'M'
        created_by   = data.get('user_id', 0)

        if not branch_id or not tran_date:
            return jsonify({'status': 'error', 'message': 'branch_id and tran_date are required'}), 400

        db  = get_db()
        cur = db.cursor(dictionary=True)
        _ensure_table(cur)
        db.commit()

        cur.execute("""
            INSERT INTO weight_tran
              (tran_date, branch_id, spell_id, emp_code, emp_name,
               gross_weight, tare_weight, net_weight, weight_type, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (tran_date, branch_id, spell_id, emp_code, emp_name,
              gross_weight, tare_weight, net_weight, weight_type, created_by))
        db.commit()
        new_id = cur.lastrowid
        cur.close(); db.close()
        return jsonify({'status': 'success', 'message': 'Saved successfully', 'id': new_id})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── DELETE /weight-transactions/<id> ─────────────────────────────────
@weight_bp.route('/weight-transactions/<int:tid>', methods=['DELETE'])
def delete_weight_transaction(tid):
    try:
        db  = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM weight_tran WHERE id = %s", (tid,))
        db.commit()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
