"""
Other Entries module endpoints (Production → Finishing Entry → Other Entries).
Table: tbl_daily_finishing
Columns: tran_date, spell_id, looms, cuts, hemming, heracle, cutting, branding,
         hand_sewer, bales, issue_bales, updated_by, updated_date_time
"""
from flask import request, jsonify
from . import otherentries_bp
from src.database import get_db


_MIGRATED = False


def _ensure_columns():
    """Add cutting / branding / issue_bales columns if they don't exist yet."""
    global _MIGRATED
    if _MIGRATED:
        return
    try:
        db = get_db()
        cursor = db.cursor()
        for col in ('cutting', 'branding', 'issue_bales'):
            try:
                cursor.execute(
                    f"ALTER TABLE tbl_daily_finishing ADD COLUMN {col} INT DEFAULT NULL"
                )
                db.commit()
            except Exception:
                # column already exists (or other benign error) — ignore
                pass
        cursor.close()
        db.close()
        _MIGRATED = True
    except Exception as e:
        print(f"[otherentries] migration check failed (non-fatal): {e}")


def _to_int(v):
    if v is None or v == '':
        return None
    try:
        return int(float(v))
    except Exception:
        return None


@otherentries_bp.route('/entry', methods=['POST'])
def save_other_entry():
    try:
        _ensure_columns()
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        tran_date = data.get('date')
        spell_id  = data.get('spell_id')
        user_id   = data.get('user_id')

        if not tran_date or not spell_id:
            return jsonify({'status': 'error',
                            'message': 'date and spell_id are required',
                            'received': data}), 400

        looms       = _to_int(data.get('looms'))
        cuts        = _to_int(data.get('cuts'))
        hemming     = _to_int(data.get('hemming'))
        heracle     = _to_int(data.get('heracle'))
        cutting     = _to_int(data.get('cutting'))
        branding    = _to_int(data.get('branding'))
        hand_sewer  = _to_int(data.get('hand_sewer'))
        bales       = _to_int(data.get('bales'))
        issue_bales = _to_int(data.get('issue_bales'))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO tbl_daily_finishing
                (tran_date, spell_id, looms, cuts, hemming, heracle,
                 cutting, branding, hand_sewer, bales, issue_bales, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (tran_date, spell_id, looms, cuts, hemming, heracle,
              cutting, branding, hand_sewer, bales, issue_bales, user_id))
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Saved', 'id': new_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@otherentries_bp.route('/entry', methods=['GET'])
def list_other_entries():
    try:
        _ensure_columns()
        date_str = request.args.get('date')
        spell_id = request.args.get('spell_id', type=int)
        if not date_str:
            return jsonify({'status': 'error', 'message': 'date is required'}), 400

        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT f.tbl_daily_fng_id  AS id,
                   f.tran_date         AS entry_date,
                   f.spell_id,
                   COALESCE(s.spell_name, '') AS spell_name,
                   f.looms,
                   f.cuts,
                   f.hemming,
                   f.heracle,
                   f.cutting,
                   f.branding,
                   f.hand_sewer,
                   f.bales,
                   f.issue_bales
            FROM tbl_daily_finishing f
            LEFT JOIN spell_mst s ON f.spell_id = s.spell_id
            WHERE f.tran_date = %s
        """
        params = [date_str]
        if spell_id:
            query += " AND f.spell_id = %s"
            params.append(spell_id)
        query += " ORDER BY f.tbl_daily_fng_id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        for r in rows:
            if r.get('entry_date') is not None:
                r['entry_date'] = r['entry_date'].isoformat()
        return jsonify({'status': 'success', 'entries': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@otherentries_bp.route('/entry/<int:entry_id>', methods=['PUT'])
def update_other_entry(entry_id):
    try:
        _ensure_columns()
        data = request.get_json(silent=True) or {}
        sets = []
        params = []
        for src_key, col in [
            ('spell_id',    'spell_id'),
            ('looms',       'looms'),
            ('cuts',        'cuts'),
            ('hemming',     'hemming'),
            ('heracle',     'heracle'),
            ('cutting',     'cutting'),
            ('branding',    'branding'),
            ('hand_sewer',  'hand_sewer'),
            ('bales',       'bales'),
            ('issue_bales', 'issue_bales'),
            ('user_id',     'updated_by'),
        ]:
            if src_key in data:
                sets.append(f"{col} = %s")
                params.append(_to_int(data.get(src_key)))
        if 'date' in data:
            sets.append("tran_date = %s")
            params.append(data.get('date'))
        if not sets:
            return jsonify({'status': 'error', 'message': 'no fields to update'}), 400
        sets.append("updated_date_time = CURRENT_TIMESTAMP")
        params.append(entry_id)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            f"UPDATE tbl_daily_finishing SET {', '.join(sets)} WHERE tbl_daily_fng_id = %s",
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


@otherentries_bp.route('/entry/<int:entry_id>', methods=['DELETE'])
def delete_other_entry(entry_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM tbl_daily_finishing WHERE tbl_daily_fng_id = %s",
            (entry_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'status': 'success', 'message': 'Deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
