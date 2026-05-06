"""Spinning Doff entry endpoints.

Tables (sjm database):
  - daily_doff_tbl       (header rows, columns: daily_doff_tbl_id, doff_date, spell,
                          mc_id, quality_id, trolly_id, gross_weight,
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


# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _to_str(v):
    if v is None:
        return None
    if hasattr(v, 'strftime'):
        try:
            return v.strftime('%Y-%m-%d')
        except Exception:
            return str(v)
    return str(v)


# â”€â”€ GET /spells â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@doff_bp.route('/spells', methods=['GET'])
def get_spells():
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        branch_id = request.args.get('branch_id', type=int)
        #print('Received branch_id for spells:', branch_id)
        params = []
        if branch_id:
            sql = """
            SELECT sm.spell_id, sm.spell_name
            FROM spell_mst sm
            JOIN shift_mst sh ON sh.shift_id = sm.shift_id
            WHERE (sm.status IS NULL OR sm.status = 1)
              AND sh.branch_id = %s"""
            params.append(branch_id)
        else:
            sql = """
            SELECT spell_id, spell_name
            FROM spell_mst
            WHERE (status IS NULL OR status = 1)"""
        sql += " ORDER BY spell_name"
        #print('Executing SQL:', sql, 'with params:', params)
            
        try:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        except Exception as ex:
            #print('spells query error:', ex)
            rows = []
        cur.close(); db.close()
        return jsonify({'status': 'success', 'spells': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ GET /doff/machines â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@doff_bp.route('/doff/machines', methods=['GET'])
def get_doff_machines():
    try:
        branch_id = request.args.get('branch_id', type=int)
        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT m.machine_id   AS mc_id,
                   m.machine_name AS mc_name,
                   m.mech_code    AS mc_code,
                   m.dept_id
            FROM machine_mst m
        params = []
        if branch_id:
            sql += """
            sql += """
                INNER JOIN dept_mst dm ON dm.dept_id = m.dept_id
                WHERE (m.active IS NULL OR m.active = 1)
                  AND dm.branch_id = %s
            """
            params.append(branch_id)
        else:
            sql += " WHERE (m.active IS NULL OR m.active = 1)"
        sql += " ORDER BY m.machine_name"
            """
            params.append(branch_id)
        else:
            sql += " WHERE (m.active IS NULL OR m.active = 1)"
        sql += " ORDER BY m.machine_name"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'machines': rows})
# â”€â”€ GET /doff/qualities â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ GET /doff/qualities â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@doff_bp.route('/doff/qualities', methods=['GET'])
def get_doff_qualities():
    try:
        branch_id = request.args.get('branch_id', type=int)
        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
               SELECT spg_quality_mst_id AS quality_id,
                   concat(stm.spg_type_name,'-',spg_quality,' ',sqm.no_of_spindles,' Spindles'  )        AS quality_name 
            FROM spinning_quality_mst sqm
			left join spinning_type_mst stm on stm.spg_type_mst_id =sqm.spg_type_id 
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
# â”€â”€ GET /doff/trollies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ GET /doff/trollies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
# â”€â”€ GET /doff-transactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ GET /doff-transactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
            WHERE (d.active IS NULL OR d.active = 1)
        """
        params = []
        if date_q:
            sql += " AND d.doff_date = %s"; params.append(date_q)
        if spell_id:
            sql += " AND d.spell = %s";     params.append(spell_id)
        if branch_id:
        #print('GET /doff-transactions SQL:', sql)
        #print('GET /doff-transactions params:', params)
            sql += " AND d.mc_id = %s";     params.append(mc_id)
        sql += " ORDER BY d.doff_date DESC, d.daily_doff_tbl_id DESC"
        #print('GET /doff-transactions row count:', len(rows))
        #print('GET /doff-transactions SQL:', sql)
        #print('GET /doff-transactions params:', params)
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        #print('GET /doff-transactions row count:', len(rows))

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
# â”€â”€ GET /doff/last-by-machine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ GET /doff/last-by-machine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
# â”€â”€ POST /doff-transactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ POST /doff-transactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@doff_bp.route('/doff-transactions', methods=['POST'])
def save_doff_transaction():
    """Insert (no id) or update (id provided) a doff entry."""
    try:
        data = request.json or {}
        rec_id       = data.get('id')
        doff_date    = data.get('doff_date')
        spell_id     = data.get('spell_id')
        mc_id        = data.get('mc_id')
        #print ('Received doff transaction data:', data)
        #print ('Parsed doff transaction values:', doff_date, spell_id, mc_id, quality_id, trolly_id, gross_weight, tare_weight, net_weight)
        quality_id   = data.get('quality_id')
        trolly_id    = data.get('trolly_id')
        gross_weight = data.get('gross_weight') or 0
        tare_weight  = data.get('tare_weight')  or 0
        net_weight   = data.get('net_weight')
        #print ('Received doff transaction data:', data)
        #print ('Parsed doff transaction values:', doff_date, spell_id, mc_id, quality_id, trolly_id, gross_weight, tare_weight, net_weight)
        if net_weight is None:
            try:
        if not doff_date or not spell_id or not mc_id or not trolly_id or not branch_id:
            except Exception:
                            'message': 'doff_date, spell_id, mc_id, trolly_id and branch_id are required'}), 400
        weight_type  = (data.get('weight_type') or '').strip() or None
        branch_id    = data.get('branch_id')
        user_id      = data.get('user_id') or 0

        if not doff_date or not spell_id or not mc_id or not trolly_id or not branch_id:
            return jsonify({'status': 'error',
                            'message': 'doff_date, spell_id, mc_id, trolly_id and branch_id are required'}), 400

        db = get_db()
        cur = db.cursor()
        now = datetime.now()

        if rec_id:
            sql = """
                UPDATE daily_doff_tbl SET
                    doff_date = %s, spell = %s, mc_id = %s, quality_id = %s,
                    trolly_id = %s,
                    gross_weight = %s, tare_weight = %s, net_weight = %s,
            #print('POST /doff-transactions UPDATE SQL:', sql)
            #print('POST /doff-transactions UPDATE params:', params)
                WHERE daily_doff_tbl_id = %s
            """
            params = (doff_date, spell_id, mc_id, quality_id, trolly_id,
                      gross_weight, tare_weight, net_weight, weight_type, branch_id,
                      user_id, now, rec_id)
                    (doff_date, spell, mc_id,  trolly_id,
            #print('POST /doff-transactions UPDATE params:', params)
                     updated_by,     updated_date_time, weight_type)
            saved_id = rec_id
                    (%s, %s, %s, %s,
            sql = """
                     %s, %s, 'M')
                    (doff_date, spell, mc_id,  trolly_id,
            params = (doff_date, spell_id, mc_id, trolly_id,
                     updated_by,     updated_date_time, weight_type)
                      user_id, now)
            #print('POST /doff-transactions INSERT SQL:', sql)
            #print('POST /doff-transactions INSERT params:', params)
                     %s, %s, 'M')
            """
            params = (doff_date, spell_id, mc_id, trolly_id,
                      gross_weight, tare_weight, net_weight, branch_id,
                      user_id, now)
            #print('POST /doff-transactions INSERT SQL:', sql)
            #print('POST /doff-transactions INSERT params:', params)
            cur.execute(sql, params)
            saved_id = cur.lastrowid

        db.commit()
        cur.close(); db.close()
        return jsonify({'status': 'success',
# â”€â”€ DELETE /doff-transactions/<id> â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        'id': saved_id})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# â”€â”€ DELETE /doff-transactions/<id> â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@doff_bp.route('/doff-transactions/<int:rec_id>', methods=['DELETE'])
def delete_doff_transaction(rec_id):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM daily_doff_tbl WHERE daily_doff_tbl_id = %s",

# -- NEW DOFF ENTRY ENDPOINTS --

# -- GET /doff/validate-machine -----------------------------------------------
@doff_bp.route('/doff/validate-machine', methods=['GET'])
def validate_doff_machine():
    """Validate a typed machine number/code against machine_mst.

    Accepts ?mc_no=<number-or-code>&branch_id=<id>. Looks up by mech_code
    (preferred) or machine_name. Also returns the trolly whose
    trolly_posting_code = machine.mech_posting_code (same branch when
    given) so the client can pre-fill the trolly input.
    """
    try:
        mc_no = (request.args.get('mc_no') or '').strip()
        branch_id = request.args.get('branch_id', type=int)
        if not mc_no:
            return jsonify({'status': 'error', 'message': 'mc_no required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        if branch_id:
            sql = """
                SELECT m.machine_id        AS mc_id,
                       m.mech_code         AS mc_no,
                       m.machine_name      AS mc_name,
                       m.mech_code         AS mc_code,
                       m.mech_posting_code AS mech_posting_code,
                       t.trolly_id            AS trolly_id,
                       t.trolly_name          AS trolly_name,
                       t.trolly_posting_code  AS trolly_posting_code,
                       t.trolly_weight        AS trolly_weight,
                       t.busket_weight        AS bucket_weight
                FROM machine_mst m
                INNER JOIN dept_mst dm ON dm.dept_id = m.dept_id
                LEFT JOIN trolly_mst t
                       ON t.trolly_posting_code = m.mech_posting_code
                      AND (t.branch_id IS NULL OR t.branch_id = %s)
                WHERE (m.active IS NULL OR m.active = 1)
                  AND dm.branch_id = %s
                  AND (m.trolly_posting_code = %s OR m.machine_name = %s)
                LIMIT 1
            """
            params = (branch_id, branch_id, mc_no, mc_no)
        else:
            sql = """
                SELECT m.machine_id        AS mc_id,
                       m.mech_code         AS mc_no,
                       m.machine_name      AS mc_name,
                       m.mech_code         AS mc_code,
                       m.mech_posting_code AS mech_posting_code,
                       t.trolly_id            AS trolly_id,
                       t.trolly_name          AS trolly_name,
                       t.trolly_posting_code  AS trolly_posting_code,
                       t.trolly_weight        AS trolly_weight,
                       t.busket_weight        AS bucket_weight
                FROM machine_mst m
                LEFT JOIN trolly_mst t
                       ON t.trolly_posting_code = m.mech_posting_code
                WHERE (m.active IS NULL OR m.active = 1)
                  AND (m.mech_code = %s OR m.machine_name = %s)
                LIMIT 1
            """
            params = (mc_no, mc_no)
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close(); db.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Machine not found'}), 404

        for k in ('trolly_weight', 'bucket_weight'):
            v = row.get(k)
            if v is not None:
                try: row[k] = float(v)
                except Exception: pass

        return jsonify({
            'status':              'success',
            'mc_id':               row.get('mc_id'),
            'mc_no':               row.get('mc_no'),
            'mc_name':             row.get('mc_name'),
            'mc_code':             row.get('mc_code'),
            'mech_posting_code':   row.get('mech_posting_code'),
            'trolly_id':           row.get('trolly_id'),
            'trolly_name':         row.get('trolly_name'),
            'trolly_posting_code': row.get('trolly_posting_code'),
            'trolly_weight':       row.get('trolly_weight'),
            'bucket_weight':       row.get('bucket_weight'),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/validate-trolly ------------------------------------------------
@doff_bp.route('/doff/validate-trolly', methods=['GET'])
def validate_doff_trolly():
    """Validate a typed trolly number against trolly_mst.

    Accepts ?trolly_no=<value>&branch_id=<id>. Matches against
    trolly_posting_code (numeric) OR trolly_name. Returns trolly_id plus
    trolly + bucket weights for auto-tare.
    """
    try:
        trolly_no = (request.args.get('trolly_no') or '').strip()
        branch_id = request.args.get('branch_id', type=int)
        if not trolly_no:
            return jsonify({'status': 'error', 'message': 'trolly_no required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT trolly_id,
                   trolly_name,
                   trolly_posting_code AS trolly_no,
                   trolly_weight,
                   busket_weight AS bucket_weight
            FROM trolly_mst
            WHERE (trolly_posting_code = %s OR trolly_name = %s)
        """
        # Coerce posting code: only pass int if input is digits, else -1 (no match)
        try:
            posting_code_val = int(trolly_no)
        except ValueError:
            posting_code_val = -1
        params = [posting_code_val, trolly_no]
        if branch_id:
            sql += ' AND (branch_id IS NULL OR branch_id = %s)'
            params.append(branch_id)
        sql += ' LIMIT 1'
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        cur.close(); db.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Trolly not found'}), 404
        return jsonify({
            'status':        'success',
            'trolly_id':     row['trolly_id'],
            'trolly_no':     row['trolly_no'],
            'trolly_name':   row['trolly_name'],
            'trolly_weight': float(row['trolly_weight'] or 0),
            'bucket_weight': float(row['bucket_weight'] or 0),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/summary --------------------------------------------------------
@doff_bp.route('/doff/summary', methods=['GET'])
def get_doff_summary():
    """Return per-machine count + total net weight from daily_doff_tbl.

    Filters: ?date=YYYY-MM-DD (required), spell_id (optional),
    branch_id (optional), mc_id (optional, restricts to one machine).
    """
    try:
        d         = request.args.get('date')
        spell_id  = request.args.get('spell_id',  type=int)
        branch_id = request.args.get('branch_id', type=int)
        mc_id     = request.args.get('mc_id',     type=int)
        if not d:
            return jsonify({'status': 'error', 'message': 'date required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT d.mc_id,
                   m.mech_code    AS mc_no,
                   m.machine_name AS mc_name,
                   COUNT(*)                       AS no_of_doff,
                   COALESCE(SUM(d.net_weight), 0) AS total_wt
            FROM daily_doff_tbl d
            LEFT JOIN machine_mst m ON m.machine_id = d.mc_id
            WHERE (d.active IS NULL OR d.active = 1)
              AND d.doff_date = %s
        """
        params = [d]
        if spell_id:
            sql += ' AND d.spell = %s'
            params.append(spell_id)
        if branch_id:
            sql += ' AND d.branch_id = %s'
            params.append(branch_id)
        if mc_id:
            sql += ' AND d.mc_id = %s'
            params.append(mc_id)
        sql += ' GROUP BY d.mc_id, m.mech_code, m.machine_name ORDER BY m.mech_code'

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close(); db.close()

        out = []
        for r in rows:
            out.append({
                'mc_id':      r['mc_id'],
                'mc_no':      r['mc_no'],
                'mc_name':    r['mc_name'],
                'no_of_doff': int(r['no_of_doff'] or 0),
                'total_wt':   float(r['total_wt'] or 0),
            })
        return jsonify({'status': 'success', 'summary': out})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# -- FRAME ENTRY ENDPOINTS --

# Lazy-migration: make sure the daily_doff_frames_winding table has a
# quality_id column so spell-wise frame entry can persist quality per machine.
_FRAME_SCHEMA_OK = False

def _ensure_frame_schema():
    """Add quality_id INT NULL column to daily_doff_frames_winding if missing.

    Safe to call repeatedly; only runs the ALTER on first invocation per
    process. Errors are swallowed so the endpoints keep working when the
    column already exists or when the user lacks ALTER privileges (in which
    case the DBA must apply the migration manually).
    """
    global _FRAME_SCHEMA_OK
    if _FRAME_SCHEMA_OK:
        return
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME   = 'daily_doff_frames_winding'
               AND COLUMN_NAME  = 'quality_id'
        """)
        (exists,) = cur.fetchone()
        if not exists:
            cur.execute("""
                ALTER TABLE daily_doff_frames_winding
                  ADD COLUMN quality_id INT NULL AFTER mc_eb_id
            """)
            db.commit()
        cur.close(); db.close()
        _FRAME_SCHEMA_OK = True
    except Exception as ex:
        print('frame schema ensure failed:', ex)


# -- GET /doff/frame-machines -------------------------------------------------
@doff_bp.route('/doff/frame-machines', methods=['GET'])
def get_frame_machines():
    """List spinning-frame machines (machine_type_id = 36) for a branch."""
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT mm.machine_id   AS mc_id,
                   mm.machine_name AS mc_name,
                   mm.mech_code    AS mc_code
            FROM machine_mst mm
            LEFT JOIN dept_mst dm ON dm.dept_id = mm.dept_id
            WHERE dm.branch_id = %s
              AND mm.machine_type_id = 36
              AND (mm.active IS NULL OR mm.active = 1)
            ORDER BY mm.machine_id DESC
        """
        cur.execute(sql, (branch_id,))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'machines': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/frame-entries --------------------------------------------------
@doff_bp.route('/doff/frame-entries', methods=['GET'])
def get_frame_entries():
    """Return active frame mc_ids for a (date, spell, branch).

    spg_wdg = 'S' (spinning) for this screen.
    """
    try:
        d         = request.args.get('date')
        spell_id  = request.args.get('spell_id',  type=int)
        branch_id = request.args.get('branch_id', type=int)
        if not (d and spell_id and branch_id):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id and branch_id are required'}), 400

        _ensure_frame_schema()
        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT daily_doff_frm_wdg_id AS id,
                   mc_eb_id              AS mc_id,
                   quality_id            AS quality_id
            FROM daily_doff_frames_winding
            WHERE tran_date = %s
              AND spell     = %s
              AND branch_id = %s
              AND (spg_wdg IS NULL OR spg_wdg = 'S')
              AND (active IS NULL OR active = 1)
        """
        cur.execute(sql, (d, spell_id, branch_id))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({
            'status': 'success',
            'mc_ids': [r['mc_id'] for r in rows],
            'entries': [
                {'mc_id': r['mc_id'], 'quality_id': r.get('quality_id')}
                for r in rows
            ],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- POST /doff/frame-entries -------------------------------------------------
@doff_bp.route('/doff/frame-entries', methods=['POST'])
def save_frame_entries():
    """Bulk save: replace existing frame rows for (date, spell, branch).

    Body (preferred): {date, spell_id, branch_id, user_id,
                       entries: [{mc_id, quality_id}, ...]}
    Legacy:           {date, spell_id, branch_id, user_id, mc_ids: [int, ...]}
    Strategy: hard-delete existing rows for the key, then insert one row per
    entry with active=1, spg_wdg='S' and the chosen quality_id.
    """
    try:
        data = request.get_json(silent=True) or {}
        d         = data.get('date')
        spell_id  = data.get('spell_id')
        branch_id = data.get('branch_id')
        user_id   = data.get('user_id') or 0
        entries   = data.get('entries')
        mc_ids    = data.get('mc_ids') or []
        if not (d and spell_id and branch_id):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id and branch_id are required'}), 400

        # Normalise to a list of (mc_id, quality_id) tuples
        pairs = []
        if isinstance(entries, list):
            for e in entries:
                if not isinstance(e, dict):
                    continue
                mc = e.get('mc_id')
                if mc is None:
                    continue
                try:
                    pairs.append((int(mc), int(e['quality_id'])
                                  if e.get('quality_id') is not None else None))
                except (TypeError, ValueError):
                    pass
        elif isinstance(mc_ids, list):
            for mc in mc_ids:
                try:
                    pairs.append((int(mc), None))
                except (TypeError, ValueError):
                    pass
        else:
            return jsonify({'status': 'error',
                            'message': 'entries must be an array'}), 400

        _ensure_frame_schema()
        db = get_db()
        cur = db.cursor()
        # Clear existing spinning frame rows for this date+spell+branch
        cur.execute("""
            DELETE FROM daily_doff_frames_winding
            WHERE tran_date = %s
              AND spell     = %s
              AND branch_id = %s
              AND (spg_wdg IS NULL OR spg_wdg = 'S')
        """, (d, spell_id, branch_id))

        inserted = 0
        if pairs:
            ins = """
                INSERT INTO daily_doff_frames_winding
                    (tran_date, spell, mc_eb_id, quality_id, spg_wdg, branch_id, active)
                VALUES (%s, %s, %s, %s, 'S', %s, 1)
            """
            for mc, qid in pairs:
                try:
                    cur.execute(ins, (d, spell_id, mc, qid, branch_id))
                    inserted += 1
                except Exception as ex:
                    print('frame insert err for mc', mc, ex)

        db.commit()
        cur.close(); db.close()
        return jsonify({
            'status':  'success',
            'message': f'Saved {inserted} frame(s)',
            'count':   inserted,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/frame-machine-defaults ----------------------------------------
@doff_bp.route('/doff/frame-machine-defaults', methods=['GET'])
def get_frame_machine_defaults():
    """Return last-used quality_id per frame machine for a branch.

    Looks at the most recent row in daily_doff_frames_winding for each
    mc_eb_id (regardless of date / spell) where quality_id is not null.
    Falls back to the latest daily_doff_tbl row when no frame entry exists.
    Response: {status, defaults: [{mc_id, quality_id}]}
    """
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id required'}), 400

        _ensure_frame_schema()
        db = get_db()
        cur = db.cursor(dictionary=True)
        # Latest quality per machine from frame entries
        cur.execute("""
            SELECT f.mc_eb_id   AS mc_id,
                   f.quality_id AS quality_id
            FROM daily_doff_frames_winding f
            INNER JOIN (
                SELECT mc_eb_id, MAX(daily_doff_frm_wdg_id) AS max_id
                FROM daily_doff_frames_winding
                WHERE branch_id = %s
                  AND quality_id IS NOT NULL
                  AND (spg_wdg IS NULL OR spg_wdg = 'S')
                GROUP BY mc_eb_id
            ) lf ON lf.mc_eb_id = f.mc_eb_id
               AND lf.max_id   = f.daily_doff_frm_wdg_id
        """, (branch_id,))
        defaults = {row['mc_id']: row['quality_id'] for row in cur.fetchall()
                    if row.get('quality_id') is not None}

        # Fallback: latest quality per machine from doff transactions for any
        # frame machines not yet covered above.
        cur.execute("""
            SELECT d.mc_id      AS mc_id,
                   d.quality_id AS quality_id
            FROM daily_doff_tbl d
            INNER JOIN (
                SELECT mc_id, MAX(daily_doff_tbl_id) AS max_id
                FROM daily_doff_tbl
                WHERE branch_id = %s
                  AND quality_id IS NOT NULL
                  AND (active IS NULL OR active = 1)
                GROUP BY mc_id
            ) ld ON ld.mc_id  = d.mc_id
               AND ld.max_id = d.daily_doff_tbl_id
        """, (branch_id,))
        for row in cur.fetchall():
            qid = row.get('quality_id')
            mc  = row.get('mc_id')
            if mc is not None and qid is not None and mc not in defaults:
                defaults[mc] = qid

        cur.close(); db.close()
        return jsonify({
            'status': 'success',
            'defaults': [{'mc_id': mc, 'quality_id': qid}
                         for mc, qid in defaults.items()],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    (rec_id,))
        db.commit()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'message': 'Doff entry deleted'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# -- NEW DOFF ENTRY ENDPOINTS --

# -- GET /doff/validate-machine -----------------------------------------------
@doff_bp.route('/doff/validate-machine', methods=['GET'])
def validate_doff_machine():
    """Validate a typed machine number/code against machine_mst.

    Accepts ?mc_no=<number-or-code>&branch_id=<id>. Looks up by mech_code
    (preferred) or machine_name. Also returns the trolly whose
    trolly_posting_code = machine.mech_posting_code (same branch when
    given) so the client can pre-fill the trolly input.
    """
    try:
        mc_no = (request.args.get('mc_no') or '').strip()
        branch_id = request.args.get('branch_id', type=int)
        if not mc_no:
            return jsonify({'status': 'error', 'message': 'mc_no required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        if branch_id:
            sql = """
                SELECT m.machine_id        AS mc_id,
                       m.mech_code         AS mc_no,
                       m.machine_name      AS mc_name,
                       m.mech_code         AS mc_code,
                       m.mech_posting_code AS mech_posting_code,
                       t.trolly_id            AS trolly_id,
                       t.trolly_name          AS trolly_name,
                       t.trolly_posting_code  AS trolly_posting_code,
                       t.trolly_weight        AS trolly_weight,
                       t.busket_weight        AS bucket_weight
                FROM machine_mst m
                INNER JOIN dept_mst dm ON dm.dept_id = m.dept_id
                LEFT JOIN trolly_mst t
                       ON t.trolly_posting_code = m.mech_posting_code
                      AND (t.branch_id IS NULL OR t.branch_id = %s)
                WHERE (m.active IS NULL OR m.active = 1)
                  AND dm.branch_id = %s
                  AND (m.trolly_posting_code = %s OR m.machine_name = %s)
                LIMIT 1
            """
            params = (branch_id, branch_id, mc_no, mc_no)
        else:
            sql = """
                SELECT m.machine_id        AS mc_id,
                       m.mech_code         AS mc_no,
                       m.machine_name      AS mc_name,
                       m.mech_code         AS mc_code,
                       m.mech_posting_code AS mech_posting_code,
                       t.trolly_id            AS trolly_id,
                       t.trolly_name          AS trolly_name,
                       t.trolly_posting_code  AS trolly_posting_code,
                       t.trolly_weight        AS trolly_weight,
                       t.busket_weight        AS bucket_weight
                FROM machine_mst m
                LEFT JOIN trolly_mst t
                       ON t.trolly_posting_code = m.mech_posting_code
                WHERE (m.active IS NULL OR m.active = 1)
                  AND (m.mech_code = %s OR m.machine_name = %s)
                LIMIT 1
            """
            params = (mc_no, mc_no)
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close(); db.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Machine not found'}), 404

        for k in ('trolly_weight', 'bucket_weight'):
            v = row.get(k)
            if v is not None:
                try: row[k] = float(v)
                except Exception: pass

        return jsonify({
            'status':              'success',
            'mc_id':               row.get('mc_id'),
            'mc_no':               row.get('mc_no'),
            'mc_name':             row.get('mc_name'),
            'mc_code':             row.get('mc_code'),
            'mech_posting_code':   row.get('mech_posting_code'),
            'trolly_id':           row.get('trolly_id'),
            'trolly_name':         row.get('trolly_name'),
            'trolly_posting_code': row.get('trolly_posting_code'),
            'trolly_weight':       row.get('trolly_weight'),
            'bucket_weight':       row.get('bucket_weight'),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/validate-trolly ------------------------------------------------
@doff_bp.route('/doff/validate-trolly', methods=['GET'])
def validate_doff_trolly():
    """Validate a typed trolly number against trolly_mst.

    Accepts ?trolly_no=<value>&branch_id=<id>. Matches against
    trolly_posting_code (numeric) OR trolly_name. Returns trolly_id plus
    trolly + bucket weights for auto-tare.
    """
    try:
        trolly_no = (request.args.get('trolly_no') or '').strip()
        branch_id = request.args.get('branch_id', type=int)
        if not trolly_no:
            return jsonify({'status': 'error', 'message': 'trolly_no required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT trolly_id,
                   trolly_name,
                   trolly_posting_code AS trolly_no,
                   trolly_weight,
                   busket_weight AS bucket_weight
            FROM trolly_mst
            WHERE (trolly_posting_code = %s OR trolly_name = %s)
        """
        # Coerce posting code: only pass int if input is digits, else -1 (no match)
        try:
            posting_code_val = int(trolly_no)
        except ValueError:
            posting_code_val = -1
        params = [posting_code_val, trolly_no]
        if branch_id:
            sql += ' AND (branch_id IS NULL OR branch_id = %s)'
            params.append(branch_id)
        sql += ' LIMIT 1'
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        cur.close(); db.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Trolly not found'}), 404
        return jsonify({
            'status':        'success',
            'trolly_id':     row['trolly_id'],
            'trolly_no':     row['trolly_no'],
            'trolly_name':   row['trolly_name'],
            'trolly_weight': float(row['trolly_weight'] or 0),
            'bucket_weight': float(row['bucket_weight'] or 0),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/summary --------------------------------------------------------
@doff_bp.route('/doff/summary', methods=['GET'])
def get_doff_summary():
    """Return per-machine count + total net weight from daily_doff_tbl.

    Filters: ?date=YYYY-MM-DD (required), spell_id (optional),
    branch_id (optional), mc_id (optional, restricts to one machine).
    """
    try:
        d         = request.args.get('date')
        spell_id  = request.args.get('spell_id',  type=int)
        branch_id = request.args.get('branch_id', type=int)
        mc_id     = request.args.get('mc_id',     type=int)
        if not d:
            return jsonify({'status': 'error', 'message': 'date required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT d.mc_id,
                   m.mech_code    AS mc_no,
                   m.machine_name AS mc_name,
                   COUNT(*)                       AS no_of_doff,
                   COALESCE(SUM(d.net_weight), 0) AS total_wt
            FROM daily_doff_tbl d
            LEFT JOIN machine_mst m ON m.machine_id = d.mc_id
            WHERE (d.active IS NULL OR d.active = 1)
              AND d.doff_date = %s
        """
        params = [d]
        if spell_id:
            sql += ' AND d.spell = %s'
            params.append(spell_id)
        if branch_id:
            sql += ' AND d.branch_id = %s'
            params.append(branch_id)
        if mc_id:
            sql += ' AND d.mc_id = %s'
            params.append(mc_id)
        sql += ' GROUP BY d.mc_id, m.mech_code, m.machine_name ORDER BY m.mech_code'

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close(); db.close()

        out = []
        for r in rows:
            out.append({
                'mc_id':      r['mc_id'],
                'mc_no':      r['mc_no'],
                'mc_name':    r['mc_name'],
                'no_of_doff': int(r['no_of_doff'] or 0),
                'total_wt':   float(r['total_wt'] or 0),
            })
        return jsonify({'status': 'success', 'summary': out})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# -- FRAME ENTRY ENDPOINTS --

# -- GET /doff/frame-machines -------------------------------------------------
@doff_bp.route('/doff/frame-machines', methods=['GET'])
def get_frame_machines():
    """List spinning-frame machines (machine_type_id = 36) for a branch."""
    try:
        branch_id = request.args.get('branch_id', type=int)
        if not branch_id:
            return jsonify({'status': 'error', 'message': 'branch_id required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT mm.machine_id   AS mc_id,
                   mm.machine_name AS mc_name,
                   mm.mech_code    AS mc_code
            FROM machine_mst mm
            LEFT JOIN dept_mst dm ON dm.dept_id = mm.dept_id
            WHERE dm.branch_id = %s
              AND mm.machine_type_id = 36
              AND (mm.active IS NULL OR mm.active = 1)
            ORDER BY mm.machine_id DESC
        """
        cur.execute(sql, (branch_id,))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({'status': 'success', 'machines': rows})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- GET /doff/frame-entries --------------------------------------------------
@doff_bp.route('/doff/frame-entries', methods=['GET'])
def get_frame_entries():
    """Return active frame mc_ids for a (date, spell, branch).

    spg_wdg = 'S' (spinning) for this screen.
    """
    try:
        d         = request.args.get('date')
        spell_id  = request.args.get('spell_id',  type=int)
        branch_id = request.args.get('branch_id', type=int)
        if not (d and spell_id and branch_id):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id and branch_id are required'}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)
        sql = """
            SELECT daily_doff_frm_wdg_id AS id,
                   mc_eb_id              AS mc_id
            FROM daily_doff_frames_winding
            WHERE tran_date = %s
              AND spell     = %s
              AND branch_id = %s
              AND (spg_wdg IS NULL OR spg_wdg = 'S')
              AND (active IS NULL OR active = 1)
        """
        cur.execute(sql, (d, spell_id, branch_id))
        rows = cur.fetchall()
        cur.close(); db.close()
        return jsonify({
            'status': 'success',
            'mc_ids': [r['mc_id'] for r in rows],
            'entries': rows,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -- POST /doff/frame-entries -------------------------------------------------
@doff_bp.route('/doff/frame-entries', methods=['POST'])
def save_frame_entries():
    """Bulk save: replace existing frame rows for (date, spell, branch).

    Body: {date, spell_id, branch_id, user_id, mc_ids: [int, ...]}
    Strategy: soft-delete (active=0) all existing rows for the key,
    then insert one row per mc_id with active=1, spg_wdg='S'.
    """
    try:
        data = request.get_json(silent=True) or {}
        d         = data.get('date')
        spell_id  = data.get('spell_id')
        branch_id = data.get('branch_id')
        user_id   = data.get('user_id') or 0
        mc_ids    = data.get('mc_ids') or []
        if not (d and spell_id and branch_id):
            return jsonify({'status': 'error',
                            'message': 'date, spell_id and branch_id are required'}), 400
        if not isinstance(mc_ids, list):
            return jsonify({'status': 'error',
                            'message': 'mc_ids must be an array'}), 400

        db = get_db()
        cur = db.cursor()
        # Clear existing spinning frame rows for this date+spell+branch
        cur.execute("""
            DELETE FROM daily_doff_frames_winding
            WHERE tran_date = %s
              AND spell     = %s
              AND branch_id = %s
              AND (spg_wdg IS NULL OR spg_wdg = 'S')
        """, (d, spell_id, branch_id))

        inserted = 0
        if mc_ids:
            ins = """
                INSERT INTO daily_doff_frames_winding
                    (tran_date, spell, mc_eb_id, spg_wdg, branch_id, active)
                VALUES (%s, %s, %s, 'S', %s, 1)
            """
            for mc in mc_ids:
                try:
                    cur.execute(ins, (d, spell_id, int(mc), branch_id))
                    inserted += 1
                except Exception as ex:
                    print('frame insert err for mc', mc, ex)

        db.commit()
        cur.close(); db.close()
        return jsonify({
            'status':  'success',
            'message': f'Saved {inserted} frame(s)',
            'count':   inserted,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

