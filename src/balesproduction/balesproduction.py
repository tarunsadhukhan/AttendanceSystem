"""
Bales Production module endpoints.

Currently houses the Roll Stock screen — table tbl_daily_roll_stock.
Uses the project standard: mysql.connector via src.database.get_db.
"""
from flask import request, jsonify
from . import balesproduction_bp
from src.database import get_db


# ─────────────────────────────────────────────────────────────────────────────
# Master lookups
# ─────────────────────────────────────────────────────────────────────────────

@balesproduction_bp.route('/mc-codes', methods=['GET'])
def get_mc_codes():
    """
    Machine codes for Roll Stock screen.
    Source: mechine_code_master, filtered by branch_id and is_active.
    Query params: ?branch_id=<id> (required)
    Returns: { status, machines: [ { mc_code_id, mc_code, mechine_type_name } ] }
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT mc_code_id,
                   mc_code,
                   Mechine_type_name AS mechine_type_name,
                   dept_id,
                   machine_type,
                   shed_type
            FROM mechine_code_master
            WHERE branch_id = %s
              AND (is_active IS NULL OR is_active = 1)
            ORDER BY order_no
        """, (branch_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'machines': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Roll Stock — table: tbl_daily_roll_stock
# ─────────────────────────────────────────────────────────────────────────────

@balesproduction_bp.route('/roll-stock', methods=['POST'])
def save_roll_stock():
    """
    Save a Roll Stock row into tbl_daily_roll_stock.
    Body JSON: { date, spell_id, mc_code_id, sprd_quality_id, no_of_rolls,
                 branch_id (optional, ignored if column absent), user_id }
    """
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        stock_date      = data.get('date')
        spell_id        = data.get('spell_id')
        mc_code_id      = data.get('mc_code_id')
        sprd_quality_id = data.get('sprd_quality_id')
        no_of_rolls     = data.get('no_of_rolls')
        shed_type       = data.get('shed_type')
        user_id         = data.get('user_id')

        missing = [k for k, v in {
            'date': stock_date, 'spell_id': spell_id,
            'mc_code_id': mc_code_id, 'sprd_quality_id': sprd_quality_id,
            'no_of_rolls': no_of_rolls,
        }.items() if v in (None, '', 0, '0')]
        if missing:
            return jsonify({'status': 'error',
                            'message': f'missing/empty: {", ".join(missing)}',
                            'received': data}), 400
        try:
            no_of_rolls = int(float(no_of_rolls))
        except Exception:
            return jsonify({'status': 'error', 'message': 'no_of_rolls must be numeric'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO tbl_daily_roll_stock
                (stock_date, spell_id, sprd_quality_id, no_of_rolls,
                 mc_code_id, shed_type, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (stock_date, spell_id, sprd_quality_id, no_of_rolls,
              mc_code_id, shed_type, user_id))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/roll-stock', methods=['GET'])
def list_roll_stock():
    """
    List Roll Stock entries for date + spell (+ optional branch filter via mc_code_master).
    Query params: ?date=YYYY-MM-DD&spell_id=<id>&branch_id=<id>
                  (date and spell_id required; branch_id optional)
    """
    try:
        date_str  = request.args.get('date')
        spell_id  = request.args.get('spell_id', type=int)
        branch_id = request.args.get('branch_id', type=int)
        if not all([date_str, spell_id]):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id are required'}), 400

        sql = """
            SELECT r.tbl_roll_stock_id   AS id,
                   r.stock_date,
                   r.spell_id,
                   r.mc_code_id,
                   COALESCE(mcm.mc_code, CONCAT('MC', r.mc_code_id)) AS mc_code,
                   COALESCE(mcm.Mechine_type_name, mcm.mc_code, CONCAT('MC', r.mc_code_id)) AS mc_name,
                   r.sprd_quality_id,
                   COALESCE(sjq.shr_name, sjq.sprd_jute_quality, '') AS quality,
                   r.no_of_rolls,
                   r.shed_type,
                   r.updated_by,
                   r.updated_date_time
            FROM tbl_daily_roll_stock r
            LEFT JOIN mechine_code_master   mcm ON r.mc_code_id      = mcm.mc_code_id
            LEFT JOIN sprd_jute_quality_mst sjq ON r.sprd_quality_id = sjq.sprd_jute_qlty_id
            WHERE r.stock_date = %s
              AND r.spell_id   = %s
        """
        params = [date_str, spell_id]
        if branch_id:
            sql += " AND mcm.branch_id = %s"
            params.append(branch_id)
        sql += " ORDER BY r.tbl_roll_stock_id DESC"

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/roll-stock/<int:entry_id>', methods=['PUT'])
def update_roll_stock(entry_id):
    """
    Update an existing Roll Stock row.
    Body JSON: { mc_code_id, sprd_quality_id, no_of_rolls, user_id }  (any subset).
    """
    try:
        data = request.get_json(silent=True) or {}
        mc_code_id      = data.get('mc_code_id')
        sprd_quality_id = data.get('sprd_quality_id')
        no_of_rolls     = data.get('no_of_rolls')
        shed_type       = data.get('shed_type')
        user_id         = data.get('user_id')
        try:
            no_of_rolls = int(float(no_of_rolls)) if no_of_rolls is not None else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'no_of_rolls must be numeric'}), 400

        sets = []
        params = []
        if mc_code_id      is not None: sets.append("mc_code_id = %s");      params.append(mc_code_id)
        if sprd_quality_id is not None: sets.append("sprd_quality_id = %s"); params.append(sprd_quality_id)
        if no_of_rolls     is not None: sets.append("no_of_rolls = %s");     params.append(no_of_rolls)
        if shed_type       is not None: sets.append("shed_type = %s");       params.append(shed_type)
        if user_id         is not None: sets.append("updated_by = %s");      params.append(user_id)
        if not sets:
            return jsonify({'status': 'error', 'message': 'no fields to update'}), 400
        sets.append("updated_date_time = CURRENT_TIMESTAMP")
        params.append(entry_id)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            f"UPDATE tbl_daily_roll_stock SET {', '.join(sets)} WHERE tbl_roll_stock_id = %s",
            tuple(params)
        )
        db.commit()
        rows = cursor.rowcount
        cursor.close()
        db.close()
        if rows == 0:
            return jsonify({'status': 'error', 'message': 'entry not found'}), 404
        return jsonify({'status': 'success', 'message': 'Updated', 'id': entry_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/roll-stock/<int:entry_id>', methods=['DELETE'])
def delete_roll_stock(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM tbl_daily_roll_stock WHERE tbl_roll_stock_id = %s",
            (entry_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Bales Production / Issue — masters
# ─────────────────────────────────────────────────────────────────────────────

@balesproduction_bp.route('/finishing-qualities', methods=['GET'])
def get_finishing_qualities():
    """
    Finishing qualities for Bales Production / Issue Entry screens.
    Source: tbl_finishing_quality_mst (no branch column — global master).
    Returns: { status, qualities: [ { quality_id, shr_name, quality_name,
                                      bags_yards, std_weight_bale } ] }
    """
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT tbl_fngqual_mst_id   AS quality_id,
                   COALESCE(shr_name, quality_name) AS shr_name,
                   quality_name,
                   bags_yards,
                   std_weight_bale
            FROM tbl_finishing_quality_mst
            ORDER BY shr_name, quality_name
        """)
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        for r in rows:
            if r.get('std_weight_bale') is not None:
                try: r['std_weight_bale'] = float(r['std_weight_bale'])
                except Exception: pass
        return jsonify({'status': 'success', 'qualities': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/customers', methods=['GET'])
def get_customers():
    """
    Customers for Bales Production / Issue Entry screens.
    Source: tbl_customer_mst (no branch column — global master).
    Returns: { status, customers: [ { customer_id, shr_name, customer_name } ] }
    """
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT tbl_cust_mst_id AS customer_id,
                   COALESCE(shr_name, customer_name) AS shr_name,
                   customer_name
            FROM tbl_customer_mst
            ORDER BY shr_name, customer_name
        """)
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'customers': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Bales Production Entry — table tbl_daily_bales_transaction
# ─────────────────────────────────────────────────────────────────────────────

@balesproduction_bp.route('/prod-entry', methods=['POST'])
def save_bales_prod_entry():
    """
    Save a Bales Production Entry row.
    Body JSON: { date, spell_id, fng_quality_id, customer_id,
                 prod_bales, act_bale_weight }
    std_bale_weight is auto-filled from tbl_finishing_quality_mst.
    issue_bales is stored as 0.
    """
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        tran_date       = data.get('date')
        spell_id        = data.get('spell_id')
        fng_quality_id  = data.get('fng_quality_id')
        customer_id     = data.get('customer_id')
        prod_bales      = data.get('prod_bales')
        act_bale_weight = data.get('act_bale_weight')

        missing = [k for k, v in {
            'date': tran_date, 'spell_id': spell_id,
            'fng_quality_id': fng_quality_id, 'customer_id': customer_id,
            'prod_bales': prod_bales,
        }.items() if v in (None, '', 0, '0')]
        if missing:
            return jsonify({'status': 'error',
                            'message': f'missing/empty: {", ".join(missing)}',
                            'received': data}), 400
        try:
            prod_bales = int(float(prod_bales))
        except Exception:
            return jsonify({'status': 'error', 'message': 'prod_bales must be numeric'}), 400
        try:
            act_bale_weight = float(act_bale_weight) if act_bale_weight not in (None, '') else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'act_bale_weight must be numeric'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT std_weight_bale FROM tbl_finishing_quality_mst WHERE tbl_fngqual_mst_id = %s",
            (fng_quality_id,)
        )
        row = cursor.fetchone()
        std_bale_weight = float(row['std_weight_bale']) if row and row.get('std_weight_bale') is not None else None

        ins = db.cursor()
        ins.execute("""
            INSERT INTO tbl_daily_bales_transaction
                (tran_date, spell_id, fng_quality_id, customer_id,
                 prod_bales, issue_bales, act_bale_weight, std_bale_weight)
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s)
        """, (tran_date, spell_id, fng_quality_id, customer_id,
              prod_bales, act_bale_weight, std_bale_weight))
        db.commit()
        new_id = ins.lastrowid
        ins.close()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/prod-entry', methods=['GET'])
def list_bales_prod_entries():
    """
    List Bales Production entries for date + spell.
    Query params: ?date=YYYY-MM-DD&spell_id=<id>  (both required)
    """
    try:
        date_str = request.args.get('date')
        spell_id = request.args.get('spell_id', type=int)
        if not all([date_str, spell_id]):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id are required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT t.tbl_daily_trans_id AS id,
                   t.tran_date,
                   t.spell_id,
                   t.fng_quality_id,
                   COALESCE(fq.shr_name, fq.quality_name, '') AS quality,
                   t.customer_id,
                   COALESCE(c.shr_name, c.customer_name, '')  AS customer,
                   t.prod_bales,
                   t.issue_bales,
                   t.act_bale_weight,
                   t.std_bale_weight
            FROM tbl_daily_bales_transaction t
            LEFT JOIN tbl_finishing_quality_mst fq ON t.fng_quality_id = fq.tbl_fngqual_mst_id
            LEFT JOIN tbl_customer_mst          c  ON t.customer_id    = c.tbl_cust_mst_id
            WHERE t.tran_date = %s
              AND t.spell_id  = %s
              AND COALESCE(t.prod_bales, 0) > 0
            ORDER BY t.tbl_daily_trans_id DESC
        """, (date_str, spell_id))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        for r in rows:
            for k in ('act_bale_weight', 'std_bale_weight'):
                if r.get(k) is not None:
                    try: r[k] = float(r[k])
                    except Exception: pass
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/prod-entry/<int:entry_id>', methods=['PUT'])
def update_bales_prod_entry(entry_id):
    """
    Update an existing Bales Production Entry row.
    Body JSON: { fng_quality_id, customer_id, prod_bales, act_bale_weight }
    (any subset). std_bale_weight is refreshed if fng_quality_id is provided.
    """
    try:
        data = request.get_json(silent=True) or {}
        fng_quality_id  = data.get('fng_quality_id')
        customer_id     = data.get('customer_id')
        prod_bales      = data.get('prod_bales')
        act_bale_weight = data.get('act_bale_weight')

        try:
            prod_bales = int(float(prod_bales)) if prod_bales is not None else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'prod_bales must be numeric'}), 400
        try:
            act_bale_weight = float(act_bale_weight) if act_bale_weight not in (None, '') else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'act_bale_weight must be numeric'}), 400

        sets = []
        params = []
        if fng_quality_id is not None:
            sets.append("fng_quality_id = %s"); params.append(fng_quality_id)
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute(
                "SELECT std_weight_bale FROM tbl_finishing_quality_mst WHERE tbl_fngqual_mst_id = %s",
                (fng_quality_id,)
            )
            row = cur.fetchone()
            cur.close()
            db.close()
            std_bale_weight = float(row['std_weight_bale']) if row and row.get('std_weight_bale') is not None else None
            sets.append("std_bale_weight = %s"); params.append(std_bale_weight)
        if customer_id     is not None: sets.append("customer_id = %s");     params.append(customer_id)
        if prod_bales      is not None: sets.append("prod_bales = %s");      params.append(prod_bales)
        if 'act_bale_weight' in data:   sets.append("act_bale_weight = %s"); params.append(act_bale_weight)
        if not sets:
            return jsonify({'status': 'error', 'message': 'no fields to update'}), 400
        params.append(entry_id)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            f"UPDATE tbl_daily_bales_transaction SET {', '.join(sets)} WHERE tbl_daily_trans_id = %s",
            tuple(params)
        )
        db.commit()
        rows = cursor.rowcount
        cursor.close()
        db.close()
        if rows == 0:
            return jsonify({'status': 'error', 'message': 'entry not found'}), 404
        return jsonify({'status': 'success', 'message': 'Updated', 'id': entry_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/prod-entry/<int:entry_id>', methods=['DELETE'])
def delete_bales_prod_entry(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM tbl_daily_bales_transaction WHERE tbl_daily_trans_id = %s",
            (entry_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Bales Issue Entry — same table tbl_daily_bales_transaction, issue_bales col
# ─────────────────────────────────────────────────────────────────────────────

@balesproduction_bp.route('/issue-entry', methods=['POST'])
def save_bales_issue_entry():
    """
    Save a Bales Issue Entry row.
    Body JSON: { date, spell_id, fng_quality_id, customer_id,
                 issue_bales, act_bale_weight }
    std_bale_weight is auto-filled from tbl_finishing_quality_mst.
    prod_bales is stored as 0.
    """
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        tran_date       = data.get('date')
        spell_id        = data.get('spell_id')
        fng_quality_id  = data.get('fng_quality_id')
        customer_id     = data.get('customer_id')
        issue_bales     = data.get('issue_bales')
        act_bale_weight = data.get('act_bale_weight')

        missing = [k for k, v in {
            'date': tran_date, 'spell_id': spell_id,
            'fng_quality_id': fng_quality_id, 'customer_id': customer_id,
            'issue_bales': issue_bales,
        }.items() if v in (None, '', 0, '0')]
        if missing:
            return jsonify({'status': 'error',
                            'message': f'missing/empty: {", ".join(missing)}',
                            'received': data}), 400
        try:
            issue_bales = int(float(issue_bales))
        except Exception:
            return jsonify({'status': 'error', 'message': 'issue_bales must be numeric'}), 400
        try:
            act_bale_weight = float(act_bale_weight) if act_bale_weight not in (None, '') else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'act_bale_weight must be numeric'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT std_weight_bale FROM tbl_finishing_quality_mst WHERE tbl_fngqual_mst_id = %s",
            (fng_quality_id,)
        )
        row = cursor.fetchone()
        std_bale_weight = float(row['std_weight_bale']) if row and row.get('std_weight_bale') is not None else None

        ins = db.cursor()
        ins.execute("""
            INSERT INTO tbl_daily_bales_transaction
                (tran_date, spell_id, fng_quality_id, customer_id,
                 prod_bales, issue_bales, act_bale_weight, std_bale_weight)
            VALUES (%s, %s, %s, %s, 0, %s, %s, %s)
        """, (tran_date, spell_id, fng_quality_id, customer_id,
              issue_bales, act_bale_weight, std_bale_weight))
        db.commit()
        new_id = ins.lastrowid
        ins.close()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/issue-entry', methods=['GET'])
def list_bales_issue_entries():
    """
    List Bales Issue entries for date + spell.
    Query params: ?date=YYYY-MM-DD&spell_id=<id>  (both required)
    Returns rows where issue_bales > 0.
    """
    try:
        date_str = request.args.get('date')
        spell_id = request.args.get('spell_id', type=int)
        if not all([date_str, spell_id]):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id are required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT t.tbl_daily_trans_id AS id,
                   t.tran_date,
                   t.spell_id,
                   t.fng_quality_id,
                   COALESCE(fq.shr_name, fq.quality_name, '') AS quality,
                   t.customer_id,
                   COALESCE(c.shr_name, c.customer_name, '')  AS customer,
                   t.prod_bales,
                   t.issue_bales,
                   t.act_bale_weight,
                   t.std_bale_weight
            FROM tbl_daily_bales_transaction t
            LEFT JOIN tbl_finishing_quality_mst fq ON t.fng_quality_id = fq.tbl_fngqual_mst_id
            LEFT JOIN tbl_customer_mst          c  ON t.customer_id    = c.tbl_cust_mst_id
            WHERE t.tran_date = %s
              AND t.spell_id  = %s
              AND COALESCE(t.issue_bales, 0) > 0
            ORDER BY t.tbl_daily_trans_id DESC
        """, (date_str, spell_id))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        for r in rows:
            for k in ('act_bale_weight', 'std_bale_weight'):
                if r.get(k) is not None:
                    try: r[k] = float(r[k])
                    except Exception: pass
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/issue-entry/<int:entry_id>', methods=['PUT'])
def update_bales_issue_entry(entry_id):
    """
    Update an existing Bales Issue Entry row.
    Body JSON: { fng_quality_id, customer_id, issue_bales, act_bale_weight }
    (any subset). std_bale_weight is refreshed if fng_quality_id is provided.
    """
    try:
        data = request.get_json(silent=True) or {}
        fng_quality_id  = data.get('fng_quality_id')
        customer_id     = data.get('customer_id')
        issue_bales     = data.get('issue_bales')
        act_bale_weight = data.get('act_bale_weight')

        try:
            issue_bales = int(float(issue_bales)) if issue_bales is not None else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'issue_bales must be numeric'}), 400
        try:
            act_bale_weight = float(act_bale_weight) if act_bale_weight not in (None, '') else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'act_bale_weight must be numeric'}), 400

        sets = []
        params = []
        if fng_quality_id is not None:
            sets.append("fng_quality_id = %s"); params.append(fng_quality_id)
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute(
                "SELECT std_weight_bale FROM tbl_finishing_quality_mst WHERE tbl_fngqual_mst_id = %s",
                (fng_quality_id,)
            )
            row = cur.fetchone()
            cur.close()
            db.close()
            std_bale_weight = float(row['std_weight_bale']) if row and row.get('std_weight_bale') is not None else None
            sets.append("std_bale_weight = %s"); params.append(std_bale_weight)
        if customer_id     is not None: sets.append("customer_id = %s");     params.append(customer_id)
        if issue_bales     is not None: sets.append("issue_bales = %s");     params.append(issue_bales)
        if 'act_bale_weight' in data:   sets.append("act_bale_weight = %s"); params.append(act_bale_weight)
        if not sets:
            return jsonify({'status': 'error', 'message': 'no fields to update'}), 400
        params.append(entry_id)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            f"UPDATE tbl_daily_bales_transaction SET {', '.join(sets)} WHERE tbl_daily_trans_id = %s",
            tuple(params)
        )
        db.commit()
        rows = cursor.rowcount
        cursor.close()
        db.close()
        if rows == 0:
            return jsonify({'status': 'error', 'message': 'entry not found'}), 404
        return jsonify({'status': 'success', 'message': 'Updated', 'id': entry_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/stock', methods=['GET'])
def get_bales_stock():
    """
    Quality + Customer wise bales stock = SUM(prod_bales - issue_bales),
    derived from tbl_daily_bales_transaction across all dates.
    Returns rows with positive stock only.
    """
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT tfqm.shr_name                                   AS quality,
                   tcm.shr_name                                    AS customer,
                   tfqm.std_weight_bale                            AS std_weight_bale,
                   SUM(COALESCE(tdbt.prod_bales,0) -
                       COALESCE(tdbt.issue_bales,0))               AS stock,
                   SUM(COALESCE(tdbt.prod_bales,0) -
                       COALESCE(tdbt.issue_bales,0))
                       * MAX(tdbt.std_bale_weight)                 AS std_weight
            FROM tbl_daily_bales_transaction tdbt
            LEFT JOIN tbl_finishing_quality_mst tfqm
                   ON tdbt.fng_quality_id = tfqm.tbl_fngqual_mst_id
            LEFT JOIN tbl_customer_mst tcm
                   ON tcm.tbl_cust_mst_id = tdbt.customer_id
            GROUP BY tfqm.shr_name, tfqm.std_weight_bale, tcm.shr_name
            HAVING stock <> 0
            ORDER BY tfqm.shr_name, tcm.shr_name
        """)
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        for r in rows:
            for k in ('std_weight_bale', 'std_weight'):
                if r.get(k) is not None:
                    try: r[k] = float(r[k])
                    except Exception: pass
            if r.get('stock') is not None:
                try: r['stock'] = int(r['stock'])
                except Exception: pass
        return jsonify({'status': 'success', 'rows': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/stock-pair', methods=['GET'])
def get_bales_stock_pair():
    """
    Available stock for a single (fng_quality_id, customer_id) pair.
    Stock = SUM(prod_bales - issue_bales) across all dates/spells.
    Query params: ?fng_quality_id=<id>&customer_id=<id>   (both required)
    Returns: { status, stock (int), std_weight (float) }
    """
    try:
        fng_quality_id = request.args.get('fng_quality_id', type=int)
        customer_id    = request.args.get('customer_id', type=int)
        if not (fng_quality_id and customer_id):
            return jsonify({'status': 'error',
                            'message': 'fng_quality_id and customer_id are required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT COALESCE(SUM(COALESCE(prod_bales,0) -
                                COALESCE(issue_bales,0)), 0)             AS stock,
                   COALESCE(SUM(COALESCE(prod_bales,0) -
                                COALESCE(issue_bales,0))
                            * MAX(std_bale_weight), 0)                    AS std_weight
            FROM tbl_daily_bales_transaction
            WHERE fng_quality_id = %s
              AND customer_id    = %s
        """, (fng_quality_id, customer_id))
        row = cur.fetchone() or {}
        cur.close()
        db.close()
        return jsonify({
            'status':     'success',
            'stock':      int(row.get('stock') or 0),
            'std_weight': float(row.get('std_weight') or 0.0),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@balesproduction_bp.route('/issue-entry/<int:entry_id>', methods=['DELETE'])
def delete_bales_issue_entry(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM tbl_daily_bales_transaction WHERE tbl_daily_trans_id = %s",
            (entry_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500