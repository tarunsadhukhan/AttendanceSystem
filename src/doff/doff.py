"""Spinning Doff entry endpoints.

Tables (sjm database):
  - daily_doff_tbl       (header rows, columns: daily_doff_tbl_id, doff_date, spell,
                          mc_id, quality_id, eb_id, trolly_id, gross_weight,
                          tare_weight, net_weight, active, branch_id, updated_by,
                          updated_date_time, weight_type)
  - spinning_quality_mst (spg_quality_mst_id, spg_quality, ...)
  - trolly_mst           (trolly_id, trolly_name, trolly_weight, busket_weight, ...)
  - machine_mst          (machine_id, machine_name, mech_code, ...)
  - spell_mst            (spell_id, spell_name, ...)
  - hrms_ed_official_details / hrms_ed_personal_details (employee lookup)
"""
import traceback
from datetime import datetime, date as date_cls

from flask import Blueprint, request, jsonify
from db import get_db

doff_bp = Blueprint('doff', __name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_str(v):
    if v is None:
        return None
    if hasattr(v, 'strftime'):
        try:
            return v.strftime('%Y-%m-%d')
        except Exception:
            return str(v)
    return str(v)


def _emp_name_by_eb(cursor, eb_id):
    if not eb_id:
        return None, None
    cursor.execute("""
        SELECT o.emp_code,
               TRIM(CONCAT(COALESCE(p.first_name,''),' ',
                           COALESCE(p.middle_name,''),' ',
                           COALESCE(p.last_name,''))) AS emp_name
        FROM hrms_ed_official_details o
        LEFT JOIN hrms_ed_personal_details p ON p.eb_id = o.eb_id
        WHERE o.eb_id = %s
        LIMIT 1
    """, (eb_id,))
    row = cursor.fetchone()
    if not row:
        return None, None
    return row.get('emp_code'), row.get('emp_name')


# ── GET /spells ──────────────────────────────────────────────────────────────

@doff_bp.route('/spells', methods=['GET'])
def get_spells():
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        branch_id = request.args.get('branch_id', type=int)
        sql="""
            SELECT spell_id, spell_name
            FROM spell_mst
            WHERE (status IS NULL OR status = 1)""" 
        params = []
        if branch_id:
            # machine_mst doesn't have branch_id directly; ignore filter
            pass
        sql += " ORDER BY spell_name"

            
        try:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        except Exception as ex:
            print('spells query error:', ex)
            rows = []
        cur.close(); db.close()
        return jsonify({'status': 'success', 'spells': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── GET /doff/machines ───────────────────────────────────────────────────────

@doff_bp.route('/doff/machines', methods=['GET'])
def get_doff_machines():
    try:
        branch_id = request.args.get('branch_id', type=int)
        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT machine_id   AS mc_id,
                   machine_name AS mc_name,
                   mech_code    AS mc_code,
                   dept_id
            FROM machine_mst
            WHERE (active IS NULL OR active = 1)
        """
        params = []
        if branch_id:
            # machine_mst doesn't have branch_id directly; ignore filter
            pass
        sql += " ORDER BY machine_name"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'machines': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── GET /doff/qualities ──────────────────────────────────────────────────────

@doff_bp.route('/doff/qualities', methods=['GET'])
def get_doff_qualities():
    try:
        branch_id = request.args.get('branch_id', type=int)
        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT spg_quality_mst_id AS quality_id,
                   spg_quality        AS quality_name
            FROM spinning_quality_mst
            WHERE 1=1
        """
        params = []
        if branch_id:
            sql += " AND (branch_id IS NULL OR branch_id = %s)"
            params.append(branch_id)
        sql += " ORDER BY spg_quality"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'qualities': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── GET /doff/trollies ───────────────────────────────────────────────────────

@doff_bp.route('/doff/trollies', methods=['GET'])
def get_doff_trollies():
    try:
        branch_id = request.args.get('branch_id', type=int)
        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT trolly_id,
                   trolly_name,
                   trolly_weight,
                   busket_weight AS bucket_weight
            FROM trolly_mst
            WHERE 1=1
        """
        params = []
        if branch_id:
            sql += " AND (branch_id IS NULL OR branch_id = %s)"
            params.append(branch_id)
        sql += " ORDER BY trolly_name"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        # cast decimals to float for clean JSON
        for r in rows:
            for k in ('trolly_weight', 'bucket_weight'):
                if r.get(k) is not None:
                    try: r[k] = float(r[k])
                    except Exception: pass
        cur.close(); db.close()
        return jsonify({'status': 'success', 'trollies': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── GET /doff-transactions ───────────────────────────────────────────────────

@doff_bp.route('/doff-transactions', methods=['GET'])
def list_doff_transactions():
    try:
        date_q    = request.args.get('date')
        spell_id  = request.args.get('spell_id', type=int)
        branch_id = request.args.get('branch_id', type=int)
        mc_id     = request.args.get('mc_id', type=int)

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT d.daily_doff_tbl_id   AS id,
                   d.doff_date,
                   d.spell                AS spell_id,
                   sp.spell_name,
                   d.mc_id,
                   m.machine_name         AS mc_name,
                   m.mech_code            AS mc_code,
                   d.quality_id,
                   q.spg_quality          AS quality_name,
                   d.trolly_id,
                   t.trolly_name,
                   t.trolly_weight,
                   t.busket_weight        AS bucket_weight,
                   d.eb_id,
                   o.emp_code,
                   TRIM(CONCAT(COALESCE(p.first_name,''),' ',
                               COALESCE(p.middle_name,''),' ',
                               COALESCE(p.last_name,''))) AS emp_name,
                   d.gross_weight,
                   d.tare_weight,
                   d.net_weight,
                   d.weight_type,
                   d.branch_id,
                   d.updated_by,
                   d.updated_date_time
            FROM daily_doff_tbl d
            LEFT JOIN spell_mst            sp ON sp.spell_id           = d.spell
            LEFT JOIN machine_mst          m  ON m.machine_id          = d.mc_id
            LEFT JOIN spinning_quality_mst q  ON q.spg_quality_mst_id  = d.quality_id
            LEFT JOIN trolly_mst           t  ON t.trolly_id           = d.trolly_id
            LEFT JOIN hrms_ed_official_details o ON o.eb_id            = d.eb_id
            LEFT JOIN hrms_ed_personal_details  p ON p.eb_id            = d.eb_id
            WHERE (d.active IS NULL OR d.active = 1)
        """
        params = []
        if date_q:
            sql += " AND d.doff_date = %s"; params.append(date_q)
        if spell_id:
            sql += " AND d.spell = %s";     params.append(spell_id)
        if branch_id:
            sql += " AND d.branch_id = %s"; params.append(branch_id)
        if mc_id:
            sql += " AND d.mc_id = %s";     params.append(mc_id)
        sql += " ORDER BY d.doff_date DESC, d.daily_doff_tbl_id DESC"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        out = []
        for r in rows:
            r['doff_date'] = _to_str(r.get('doff_date'))
            ud = r.get('updated_date_time')
            if ud and hasattr(ud, 'strftime'):
                r['updated_date_time'] = ud.strftime('%Y-%m-%d %H:%M')
            for k in ('gross_weight', 'tare_weight', 'net_weight',
                      'trolly_weight', 'bucket_weight'):
                v = r.get(k)
                if v is not None:
                    try: r[k] = float(v)
                    except Exception: pass
            out.append(r)

        cur.close(); db.close()
        return jsonify({'status': 'success', 'transactions': out})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── GET /doff/last-by-machine ────────────────────────────────────────────────

@doff_bp.route('/doff/last-by-machine', methods=['GET'])
def get_doff_last_by_machine():
    """Return last quality_id and trolly_id used for a given machine in the
    daily_doff_tbl."""
    try:
        mc_id = request.args.get('mc_id', type=int)
        if not mc_id:
            return jsonify({'status': 'error', 'message': 'mc_id required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT d.quality_id, q.spg_quality AS quality_name,
                   d.trolly_id,  t.trolly_name,
                   t.trolly_weight, t.busket_weight AS bucket_weight
            FROM daily_doff_tbl d
            LEFT JOIN spinning_quality_mst q ON q.spg_quality_mst_id = d.quality_id
            LEFT JOIN trolly_mst           t ON t.trolly_id          = d.trolly_id
            WHERE d.mc_id = %s
            ORDER BY d.doff_date DESC, d.daily_doff_tbl_id DESC
            LIMIT 1
        """, (mc_id,))
        row = cur.fetchone() or {}
        for k in ('trolly_weight', 'bucket_weight'):
            v = row.get(k)
            if v is not None:
                try: row[k] = float(v)
                except Exception: pass
        cur.close(); db.close()
        return jsonify({'status': 'success', **row})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── GET /doff/last-emp ───────────────────────────────────────────────────────

@doff_bp.route('/doff/last-emp', methods=['GET'])
def get_doff_last_emp():
    """Return last employee used for a (date, spell_id) combination."""
    try:
        date_q   = request.args.get('date')
        spell_id = request.args.get('spell_id', type=int)
        if not date_q or not spell_id:
            return jsonify({'status': 'error',
                            'message': 'date and spell_id required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT d.eb_id
            FROM daily_doff_tbl d
            WHERE d.doff_date = %s AND d.spell = %s
            ORDER BY d.daily_doff_tbl_id DESC
            LIMIT 1
        """, (date_q, spell_id))
        row = cur.fetchone() or {}
        eb_id = row.get('eb_id')
        emp_code, emp_name = _emp_name_by_eb(cur, eb_id)
        cur.close(); db.close()
        return jsonify({
            'status': 'success',
            'eb_id':    eb_id,
            'emp_code': emp_code,
            'emp_name': emp_name,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── POST /doff-transactions ──────────────────────────────────────────────────

@doff_bp.route('/doff-transactions', methods=['POST'])
def save_doff_transaction():
    """Insert (no id) or update (id provided) a doff entry."""
    try:
        data = request.json or {}
        rec_id       = data.get('id')
        doff_date    = data.get('doff_date')
        spell_id     = data.get('spell_id')
        mc_id        = data.get('mc_id')
        quality_id   = data.get('quality_id')
        trolly_id    = data.get('trolly_id')
        eb_id        = data.get('eb_id')
        gross_weight = data.get('gross_weight') or 0
        tare_weight  = data.get('tare_weight')  or 0
        net_weight   = data.get('net_weight')
        if net_weight is None:
            try:
                net_weight = float(gross_weight) - float(tare_weight)
            except Exception:
                net_weight = 0
        weight_type  = (data.get('weight_type') or '').strip() or None
        branch_id    = data.get('branch_id')
        user_id      = data.get('user_id') or 0

        if not doff_date or not spell_id or not mc_id or not eb_id:
            return jsonify({'status': 'error',
                            'message': 'doff_date, spell_id, mc_id and eb_id are required'}), 400

        db = get_db()
        cur = db.cursor()
        now = datetime.now()

        if rec_id:
            cur.execute("""
                UPDATE daily_doff_tbl SET
                    doff_date = %s, spell = %s, mc_id = %s, quality_id = %s,
                    trolly_id = %s, eb_id = %s,
                    gross_weight = %s, tare_weight = %s, net_weight = %s,
                    weight_type = %s, branch_id = %s,
                    updated_by = %s, updated_date_time = %s
                WHERE daily_doff_tbl_id = %s
            """, (doff_date, spell_id, mc_id, quality_id, trolly_id, eb_id,
                  gross_weight, tare_weight, net_weight, weight_type, branch_id,
                  user_id, now, rec_id))
            saved_id = rec_id
        else:
            cur.execute("""
                INSERT INTO daily_doff_tbl
                    (doff_date, spell, mc_id, quality_id, eb_id, trolly_id,
                     gross_weight, tare_weight, net_weight, active, branch_id,
                     updated_by, updated_date_time, weight_type)
                VALUES
                    (%s, %s, %s, %s, %s, %s,
                     %s, %s, %s, 1, %s,
                     %s, %s, %s)
            """, (doff_date, spell_id, mc_id, quality_id, eb_id, trolly_id,
                  gross_weight, tare_weight, net_weight, branch_id,
                  user_id, now, weight_type))
            saved_id = cur.lastrowid

        db.commit()
        cur.close(); db.close()
        return jsonify({'status': 'success',
                        'message': 'Doff entry saved successfully',
                        'id': saved_id})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── DELETE /doff-transactions/<id> ───────────────────────────────────────────

@doff_bp.route('/doff-transactions/<int:rec_id>', methods=['DELETE'])
def delete_doff_transaction(rec_id):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM daily_doff_tbl WHERE daily_doff_tbl_id = %s",
                    (rec_id,))
        db.commit()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'message': 'Doff entry deleted'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

