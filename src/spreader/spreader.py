"""
Spreader module endpoints.
Uses the project standard: mysql.connector via src.database.get_db.
"""
from flask import request, jsonify
from . import spreader_bp
from src.database import get_db




@spreader_bp.route('/machines', methods=['GET'])
def get_spreader_machines():

    """
    Spreader machines for Production / Issue Entry screens.
    Source: machine_mst (machine_type_id=8) joined with dept_mst, filtered by branch_id.
    Query params: ?branch_id=<id> (required)
    Returns: { status, machines: [ { mc_id, mc_name, mc_code, mc_short, dept_id, dept_name } ] }
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT mm.machine_id     AS mc_id,
                   mm.mech_shr_code   AS mc_name,
                   mm.mech_code      AS mc_code,
                   mm.mech_shr_code  AS mc_short,
                   mm.dept_id        AS dept_id,
                   dm.dept_desc      AS dept_name
            FROM machine_mst mm
            LEFT JOIN dept_mst dm ON mm.dept_id = dm.dept_id
            WHERE mm.machine_type_id = 8
              AND dm.branch_id = %s
              AND (mm.active IS NULL OR mm.active = 1)
            ORDER BY mm.mech_code, mm.mech_shr_code
        """, (branch_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'machines': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/qualities', methods=['GET'])
def get_spreader_qualities():
    """
    Jute qualities for Spreader Production / Issue Entry screens.
    Source: jute_quality_mst (shr_name shown as button label), filtered by branch_id.
    Query params: ?branch_id=<id> (required)
    Returns: { status, qualities: [ { quality_id, shr_name, quality_name } ] }
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
                SELECT jute_qlty_id AS quality_id,
                   COALESCE(shr_name, jute_quality) AS shr_name,
                   jute_quality
            FROM jute_quality_mst
            WHERE branch_id = %s
            ORDER BY shr_name, jute_quality

        """, (branch_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'qualities': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/sprd-qualities', methods=['GET'])
def get_spreader_sprd_qualities():
    """
    Spreader-specific jute qualities for Spreader Production Entry.
    Source: sprd_jute_quality_mst (shr_name shown as button label),
    filtered by branch_id.
    Query params: ?branch_id=<id> (required)
    Returns: { status, qualities: [ { quality_id, shr_name, quality_name } ] }
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        sql="""
            SELECT sprd_jute_qlty_id quality_id,
                   shr_name,
                   COALESCE(sprd_jute_quality , shr_name) AS quality_name
            FROM sprd_jute_quality_mst
            WHERE branch_id = %s
            ORDER BY shr_name, sprd_jute_quality 
        """
        cursor.execute(sql, (branch_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'qualities': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _ensure_sprd_quality_id_column():
    """Add sprd_quality_id column to tbl_daily_sperder if missing (one-time)."""
    try:
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("""
                ALTER TABLE tbl_daily_sperder
                ADD COLUMN sprd_quality_id INT DEFAULT NULL AFTER quality_id
            """)
            db.commit()
        except Exception:
            pass  # Column already exists
        cursor.close()
        db.close()
    except Exception as e:
        print(f"⚠️  tbl_daily_sperder.sprd_quality_id ensure error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Spreader Production Entry — table: tbl_daily_sperder
# ─────────────────────────────────────────────────────────────────────────────

@spreader_bp.route('/prod-entry', methods=['POST'])
def save_spreader_prod_entry():
    """
    Save a Spreader Production Entry row into tbl_daily_sperder.
    Body JSON: { date, spell_id, branch_id, mc_id, quality_id, sprd_quality_id,
                 production, bin_no, user_id }
        date      → tran_date  (YYYY-MM-DD)
        spell_id  → spell_id
        branch_id → branch_id
        user_id   → updated_by
        sprd_quality_id → sprd_quality_id (sprd_jute_quality_mst.quality_id)
    """
    try:
        _ensure_sprd_quality_id_column()
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        print("[spreader/prod-entry POST] content-type:", request.content_type,
              "raw:", request.get_data(as_text=True)[:500], "parsed:", data)
        tran_date       = data.get('date')
        spell_id        = data.get('spell_id')
        branch_id       = data.get('branch_id')
        mc_id           = data.get('mc_id')
        quality_id      = data.get('quality_id')
        sprd_quality_id = data.get('sprd_quality_id')
        production      = data.get('production')
        bin_no          = (data.get('bin_no') or '').strip() or None
        user_id         = data.get('user_id')

        missing = [k for k, v in {
            'date': tran_date, 'spell_id': spell_id, 'branch_id': branch_id,
            'mc_id': mc_id, 'quality_id': quality_id,
        }.items() if v in (None, '', 0, '0')]
        if missing:
            return jsonify({'status': 'error',
                            'message': f'missing/empty: {", ".join(missing)}',
                            'received': data}), 400
        try:
            production = int(float(production)) if production is not None else 0
        except Exception:
            return jsonify({'status': 'error', 'message': 'production must be numeric'}), 400
        if sprd_quality_id in ('', 0, '0'):
            sprd_quality_id = None

        db = get_db()
        cursor = db.cursor()
        print("Inserting Spreader Production Entry:", tran_date, spell_id, branch_id,
              mc_id, quality_id, sprd_quality_id, production, bin_no, user_id)
        cursor.execute("""
            INSERT INTO tbl_daily_sperder
                (tran_date, spell_id, branch_id, mc_id, quality_id,
                 sprd_quality_id, production, issue, bin_no, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
        """, (tran_date, spell_id, branch_id, mc_id, quality_id,
              sprd_quality_id, production, bin_no, user_id))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/prod-entry', methods=['GET'])
def list_spreader_prod_entries():
    """
    List Spreader Production Entries for date + spell + branch.
    Query params: ?date=YYYY-MM-DD&spell_id=<id>&branch_id=<id>  (all required)
    """
    try:
        date_str  = request.args.get('date')
        spell_id  = request.args.get('spell_id', type=int)
        branch_id = request.args.get('branch_id', type=int)
        if not all([date_str, spell_id, branch_id]):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id, branch_id are required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        sql="""
                     SELECT s.tbl_daily_sprd_id  AS id,
                   s.tran_date          AS entry_date,
                   s.spell_id,
                   s.branch_id,
                   s.mc_id,
                   COALESCE(mm.machine_name, mm.mech_code, CONCAT('MC', s.mc_id)) AS mc_no,
                   s.quality_id,
                   COALESCE(jq.shr_name, jq.jute_quality, '')                     AS quality,
                   s.sprd_quality_id,
                   COALESCE(sjq.shr_name, sjq.sprd_jute_quality , '')                   AS sprd_quality,
                   s.bin_no,
                   s.production
            FROM tbl_daily_sperder s
            LEFT JOIN machine_mst           mm  ON s.mc_id           = mm.machine_id
            LEFT JOIN jute_quality_mst      jq  ON s.quality_id      = jq.jute_qlty_id
            LEFT JOIN sprd_jute_quality_mst sjq ON s.sprd_quality_id = sjq.sprd_jute_qlty_id 
            WHERE s.tran_date = %s
              AND s.spell_id  = %s
              AND s.branch_id = %s
              AND COALESCE(s.production, 0) > 0
            ORDER BY s.tbl_daily_sprd_id DESC
        """
        cursor.execute(sql, (date_str, spell_id, branch_id))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/prod-entry/<int:entry_id>', methods=['PUT'])
def update_spreader_prod_entry(entry_id):
    """
    Update an existing Spreader Production Entry row.
    Body JSON: { mc_id, quality_id, sprd_quality_id, production, bin_no, user_id }
    (any subset). sprd_quality_id may be null to clear.
    """
    try:
        _ensure_sprd_quality_id_column()
        data = request.get_json(silent=True) or {}
        mc_id      = data.get('mc_id')
        quality_id = data.get('quality_id')
        production = data.get('production')
        bin_no     = (data.get('bin_no') or '').strip() or None
        user_id    = data.get('user_id')
        try:
            production = int(float(production)) if production is not None else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'production must be numeric'}), 400

        sets = []
        params = []
        if mc_id      is not None: sets.append("mc_id = %s");       params.append(mc_id)
        if quality_id is not None: sets.append("quality_id = %s");  params.append(quality_id)
        if 'sprd_quality_id' in data:
            sprd_quality_id = data.get('sprd_quality_id')
            if sprd_quality_id in ('', 0, '0'):
                sprd_quality_id = None
            sets.append("sprd_quality_id = %s"); params.append(sprd_quality_id)
        if production is not None: sets.append("production = %s");  params.append(production)
        if 'bin_no' in data:       sets.append("bin_no = %s");      params.append(bin_no)
        if user_id    is not None: sets.append("updated_by = %s");  params.append(user_id)
        if not sets:
            return jsonify({'status': 'error', 'message': 'no fields to update'}), 400
        sets.append("updated_date_time = CURRENT_TIMESTAMP")
        params.append(entry_id)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            f"UPDATE tbl_daily_sperder SET {', '.join(sets)} WHERE tbl_daily_sprd_id = %s",
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


@spreader_bp.route('/prod-entry/<int:entry_id>', methods=['DELETE'])
def delete_spreader_prod_entry(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM tbl_daily_sperder WHERE tbl_daily_sprd_id = %s",
            (entry_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Spreader Issue Entry — same table tbl_daily_sperder, "issue" column
# ─────────────────────────────────────────────────────────────────────────────

@spreader_bp.route('/issue-entry', methods=['POST'])
def save_spreader_issue_entry():
    """
    Save a Spreader Issue Entry row into tbl_daily_sperder.
    Body JSON: { date, spell_id, branch_id, quality_id, issue, bin_no, user_id }
        date  → tran_date,  user_id → updated_by
    No machine selection — mc_id stored as NULL. Stores production=0, issue=<value>.
    """
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        print("[spreader/issue-entry POST] content-type:", request.content_type,
              "raw:", request.get_data(as_text=True)[:500], "parsed:", data)
        tran_date  = data.get('date')
        spell_id   = data.get('spell_id')
        branch_id  = data.get('branch_id')
        quality_id = data.get('quality_id')
        issue      = data.get('issue')
        bin_no     = (data.get('bin_no') or '').strip() or None
        user_id    = data.get('user_id')

        missing = [k for k, v in {
            'date': tran_date, 'spell_id': spell_id, 'branch_id': branch_id,
            'quality_id': quality_id,
        }.items() if v in (None, '', 0, '0')]
        if missing:
            return jsonify({'status': 'error',
                            'message': f'missing/empty: {", ".join(missing)}',
                            'received': data}), 400
        try:
            issue = int(float(issue)) if issue is not None else 0
        except Exception:
            return jsonify({'status': 'error', 'message': 'issue must be numeric'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO tbl_daily_sperder
                (tran_date, spell_id, branch_id, mc_id, sprd_quality_id,
                 production, issue, bin_no, updated_by)
            VALUES (%s, %s, %s, NULL, %s, 0, %s, %s, %s)
        """, (tran_date, spell_id, branch_id, quality_id,
              issue, bin_no, user_id))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/issue-entry', methods=['GET'])
def list_spreader_issue_entries():
    """
    List Spreader Issue Entries for date + spell + branch.
    Query params: ?date=YYYY-MM-DD&spell_id=<id>&branch_id=<id> (all required)
    """
    try:
        date_str  = request.args.get('date')
        spell_id  = request.args.get('spell_id', type=int)
        branch_id = request.args.get('branch_id', type=int)
        if not all([date_str, spell_id, branch_id]):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id, branch_id are required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
              SELECT s.tbl_daily_sprd_id  AS id,
                   s.tran_date          AS entry_date,
                   s.spell_id,
                   s.branch_id,
                   s.quality_id,
                   COALESCE(sjqm.shr_name, sjqm.sprd_jute_quality , '') AS quality,
                   s.bin_no,
                   s.issue
            FROM tbl_daily_sperder s
            LEFT JOIN jute_quality_mst jq ON s.quality_id = jq.jute_qlty_id
			left join sprd_jute_quality_mst sjqm on s.sprd_quality_id =sjqm.sprd_jute_qlty_id       WHERE s.tran_date = %s
              AND s.spell_id  = %s
              AND s.branch_id = %s
              AND COALESCE(s.issue, 0) > 0
            ORDER BY s.tbl_daily_sprd_id DESC
        """, (date_str, spell_id, branch_id))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/quality-stock', methods=['GET'])
def get_spreader_quality_stock():
    """
    Stock-on-hand (No. of Rolls) for a single quality.
    stock = sum(production - issue) across all rows for that quality.
    Query params: ?quality_id=<id> (required)
    Returns: { status, quality_id, shr_name, stock }
    """
    try:
        quality_id = request.args.get('quality_id', type=int)
        if not quality_id:
            return jsonify({'status': 'error', 'message': 'quality_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
       SELECT sjqm.sprd_jute_qlty_id  quality_id,
                   sjqm.shr_name,
                   COALESCE(SUM(tds.production - tds.issue), 0) AS stock
            FROM tbl_daily_sperder tds
			left join sprd_jute_quality_mst sjqm on sjqm.sprd_jute_qlty_id =tds.sprd_quality_id 
            LEFT JOIN jute_quality_mst jqm ON jqm.jute_qlty_id = tds.quality_id
            WHERE tds.sprd_quality_id=%s
            GROUP BY sjqm.sprd_jute_qlty_id , sjqm.shr_name
             """, (quality_id,))
        row = cursor.fetchone()
        print(f"Quality stock for quality_id={quality_id}: {row}")
        cursor.close()
        db.close()
        if row is None:
            return jsonify({'status': 'success',
                            'quality_id': quality_id,
                            'shr_name': None,
                            'stock': 0})
        return jsonify({'status': 'success',
                        'quality_id': row['quality_id'],
                        'shr_name': row['shr_name'],
                        'stock': float(row['stock'] or 0)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/quality-stock-list', methods=['GET'])
def get_spreader_quality_stock_list():
    """
    Stock-on-hand (No. of Rolls) for every sprd_quality in a branch.
    stock = sum(production - issue) grouped by sprd_quality_id for the branch.
    Query params: ?branch_id=<id> (required)
    Returns: { status, qualities: [ { quality_id, shr_name, stock } ], total }
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT tds.sprd_quality_id                              AS quality_id,
                   sjqm.shr_name                                    AS shr_name,
                   COALESCE(SUM(tds.production - tds.issue), 0)     AS stock
            FROM tbl_daily_sperder tds
            LEFT JOIN sprd_jute_quality_mst sjqm
                   ON sjqm.sprd_jute_qlty_id = tds.sprd_quality_id
            WHERE tds.branch_id = %s
              AND tds.sprd_quality_id IS NOT NULL
            GROUP BY tds.sprd_quality_id, sjqm.shr_name
            ORDER BY sjqm.shr_name
        """, (branch_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        print(f"Quality stock list for branch_id={branch_id}: {(rows)} rows")
        qualities = [{
            'quality_id': r['quality_id'],
            'shr_name':   r['shr_name'],
            'stock':      float(r['stock'] or 0),
        } for r in rows]

        return jsonify({'status': 'success', 'qualities': qualities, 'total': len(qualities)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@spreader_bp.route('/issue-entry/<int:entry_id>', methods=['PUT'])
def update_spreader_issue_entry(entry_id):
    """
    Update an existing Spreader Issue Entry row.
    Body JSON: { quality_id, issue, bin_no, user_id }  (any subset)
    """
    try:
        data = request.get_json(silent=True) or {}
        quality_id = data.get('quality_id')
        issue      = data.get('issue')
        bin_no     = (data.get('bin_no') or '').strip() or None
        user_id    = data.get('user_id')
        try:
            issue = int(float(issue)) if issue is not None else None
        except Exception:
            return jsonify({'status': 'error', 'message': 'issue must be numeric'}), 400

        sets = []
        params = []
        if quality_id is not None: sets.append("quality_id = %s");  params.append(quality_id)
        if issue      is not None: sets.append("issue = %s");       params.append(issue)
        if 'bin_no' in data:       sets.append("bin_no = %s");      params.append(bin_no)
        if user_id    is not None: sets.append("updated_by = %s");  params.append(user_id)
        if not sets:
            return jsonify({'status': 'error', 'message': 'no fields to update'}), 400
        sets.append("updated_date_time = CURRENT_TIMESTAMP")
        params.append(entry_id)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            f"UPDATE tbl_daily_sperder SET {', '.join(sets)} WHERE tbl_daily_sprd_id = %s",
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


@spreader_bp.route('/issue-entry/<int:entry_id>', methods=['DELETE'])
def delete_spreader_issue_entry(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM tbl_daily_sperder WHERE tbl_daily_sprd_id = %s",
            (entry_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500