"""
Jute Mukam Received module — endpoints (mobile / Flask port).

Ported from the vowerp3 FastAPI screen (sjmvowerp3be/src/juteProcurement/
juteMukamRecv.py). Single create/edit screen — an entry stays editable only
within 30 minutes of creation. geo_location, geo_place and mukam_photo are
captured once at entry and shown read-only afterwards.

Uses the project standard: mysql.connector via src.database.get_db.

Routes (mounted under /jute-mukam-recvd):
    GET  /jute-mukam-recvd/setup?co_id=<>     Parties, mukams, qualities, recvd list
    GET  /jute-mukam-recvd/entry/<recvd_no>   One entry + editable flag
    POST /jute-mukam-recvd/entry              Create an entry
    PUT  /jute-mukam-recvd/entry/<recvd_no>   Update an entry (within the window)
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import request, jsonify

from . import jute_mukam_recvd_bp
from src.database import get_db

# Minutes an entry stays editable after creation.
EDIT_WINDOW_MINUTES = 30


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_table():
    """Defensive: create jute_mukam_recvd if the tenant DB doesn't have it yet."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jute_mukam_recvd (
                jute_mukam_recvd     INT(11) NOT NULL AUTO_INCREMENT,
                jute_mukam_recvd_no  INT(11) DEFAULT NULL,
                recvd_date           DATE DEFAULT NULL,
                party_id             INT(11) DEFAULT NULL,
                mukam_id             INT(11) DEFAULT NULL,
                quality_id           INT(11) DEFAULT NULL,
                gross_weight         DECIMAL(10,3) DEFAULT NULL,
                tare_weight          DECIMAL(10,3) DEFAULT NULL,
                `net_weight(10,3)`   INT(11) DEFAULT NULL,
                geo_location         VARCHAR(100) DEFAULT NULL,
                geo_place            VARCHAR(255) DEFAULT NULL,
                remarks              VARCHAR(500) DEFAULT NULL,
                mukam_photo          LONGTEXT DEFAULT NULL,
                updated_by           INT(11) DEFAULT NULL,
                update_date_time     DATETIME DEFAULT NULL,
                PRIMARY KEY (jute_mukam_recvd),
                INDEX idx_jmr_no (jute_mukam_recvd_no)
            )
        """)
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"⚠️  jute_mukam_recvd ensure-table error (non-fatal): {e}")


def _dec(v):
    try:
        return Decimal(str(v)) if v not in (None, "") else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _net_weight(gross, tare):
    g = _dec(gross) or Decimal(0)
    t = _dec(tare) or Decimal(0)
    # Column is int — store the rounded difference.
    return int((g - t).to_integral_value())


def _date_str(v):
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v) if v is not None else None


def _row_payload(data, updated_by):
    return {
        "recvd_date": data.get("recvd_date") or None,
        "party_id": _int(data.get("party_id")),
        "mukam_id": _int(data.get("mukam_id")),
        "quality_id": _int(data.get("quality_id")),
        "gross_weight": _dec(data.get("gross_weight")),
        "tare_weight": _dec(data.get("tare_weight")),
        "net_weight": _net_weight(data.get("gross_weight"), data.get("tare_weight")),
        "geo_location": (data.get("geo_location") or None),
        "geo_place": (data.get("geo_place") or None),
        "remarks": (data.get("remarks") or None),
        "mukam_photo": (data.get("mukam_photo") or None),
        "updated_by": updated_by,
    }


# ─── Setup ────────────────────────────────────────────────────────────────────

@jute_mukam_recvd_bp.route('/setup', methods=['GET'])
def jute_mukam_recvd_setup():
    """Dropdown data: parties (for the company), mukams, qualities, recvd list."""
    try:
        co_id = request.args.get('co_id', type=int)
        if not co_id:
            return jsonify({'status': 'error', 'message': 'co_id is required'}), 400

        _ensure_table()
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Parties mapped to this company; fall back to all active parties if the
        # supplier→party map has no rows for the company (keeps the screen usable).
        cursor.execute("""
            SELECT DISTINCT pm.party_id, pm.supp_name AS party_name
            FROM jute_supp_party_map jspm
            JOIN party_mst pm ON pm.party_id = jspm.party_id
            WHERE jspm.co_id = %s AND (pm.active = 1 OR pm.active IS NULL)
            ORDER BY pm.supp_name
        """, (co_id,))
        parties = cursor.fetchall()
        if not parties:
            cursor.execute("""
                SELECT pm.party_id, pm.supp_name AS party_name
                FROM party_mst pm
                WHERE (pm.co_id = %s OR pm.co_id IS NULL)
                  AND (pm.active = 1 OR pm.active IS NULL)
                ORDER BY pm.supp_name
            """, (co_id,))
            parties = cursor.fetchall()

        cursor.execute("""
            SELECT mukam_id, mukam_name
            FROM jute_mukam_mst
            ORDER BY mukam_name
        """)
        mukams = cursor.fetchall()

        cursor.execute("""
            SELECT jute_qlty_id, jute_quality
            FROM jute_quality_mst
            ORDER BY jute_quality
        """)
        qualities = cursor.fetchall()

        cursor.execute("""
            SELECT jute_mukam_recvd_no, recvd_date
            FROM jute_mukam_recvd
            ORDER BY jute_mukam_recvd_no DESC
        """)
        recvd_list = []
        for r in cursor.fetchall():
            recvd_list.append({
                'jute_mukam_recvd_no': r.get('jute_mukam_recvd_no'),
                'recvd_date': _date_str(r.get('recvd_date')),
            })

        cursor.close()
        db.close()
        return jsonify({
            'status': 'success',
            'parties': parties,
            'mukams': mukams,
            'qualities': qualities,
            'recvd_list': recvd_list,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Get by recvd no ──────────────────────────────────────────────────────────

@jute_mukam_recvd_bp.route('/entry/<int:recvd_no>', methods=['GET'])
def jute_mukam_recvd_get(recvd_no):
    """One entry plus an `editable` flag (within the edit window of creation)."""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT jute_mukam_recvd, jute_mukam_recvd_no, recvd_date,
                   party_id, mukam_id, quality_id,
                   gross_weight, tare_weight, `net_weight(10,3)` AS net_weight,
                   geo_location, geo_place, remarks, mukam_photo,
                   update_date_time,
                   (update_date_time IS NOT NULL
                    AND TIMESTAMPDIFF(MINUTE, update_date_time, NOW()) <= {EDIT_WINDOW_MINUTES})
                       AS editable
            FROM jute_mukam_recvd
            WHERE jute_mukam_recvd_no = %s
        """, (recvd_no,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Entry not found'}), 404

        editable = bool(row.pop('editable', 0))
        row['recvd_date'] = _date_str(row.get('recvd_date'))
        row['update_date_time'] = _date_str(row.get('update_date_time'))
        for k in ('gross_weight', 'tare_weight'):
            if row.get(k) is not None:
                row[k] = float(row[k])
        return jsonify({'status': 'success', 'data': row, 'editable': editable})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Create ───────────────────────────────────────────────────────────────────

@jute_mukam_recvd_bp.route('/entry', methods=['POST'])
def jute_mukam_recvd_create():
    """Create an entry. Body JSON carries the form fields + user_id."""
    try:
        _ensure_table()
        data = request.get_json() or {}
        if not _int(data.get('party_id')):
            return jsonify({'status': 'error', 'message': 'party_id is required'}), 400

        updated_by = _int(data.get('user_id')) or 0
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT COALESCE(MAX(jute_mukam_recvd_no), 0) + 1 FROM jute_mukam_recvd")
        next_no = int(cursor.fetchone()[0] or 1)

        p = _row_payload(data, updated_by)
        cursor.execute("""
            INSERT INTO jute_mukam_recvd
                (recvd_date, party_id, mukam_id, gross_weight, tare_weight,
                 `net_weight(10,3)`, quality_id, geo_location, geo_place,
                 updated_by, remarks, mukam_photo, jute_mukam_recvd_no,
                 update_date_time)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
        """, (
            p['recvd_date'], p['party_id'], p['mukam_id'], p['gross_weight'],
            p['tare_weight'], p['net_weight'], p['quality_id'], p['geo_location'],
            p['geo_place'], p['updated_by'], p['remarks'], p['mukam_photo'], next_no,
        ))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({
            'status': 'success',
            'message': f'Saved as Recvd No {next_no}',
            'jute_mukam_recvd_no': next_no,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Update ───────────────────────────────────────────────────────────────────

@jute_mukam_recvd_bp.route('/entry/<int:recvd_no>', methods=['PUT'])
def jute_mukam_recvd_update(recvd_no):
    """
    Update an entry — only within EDIT_WINDOW_MINUTES of creation.
    geo_location / geo_place / mukam_photo are capture-once, never updated.
    """
    try:
        data = request.get_json() or {}
        updated_by = _int(data.get('user_id')) or 0

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT jute_mukam_recvd,
                   (update_date_time IS NOT NULL
                    AND TIMESTAMPDIFF(MINUTE, update_date_time, NOW()) <= {EDIT_WINDOW_MINUTES})
                       AS editable
            FROM jute_mukam_recvd
            WHERE jute_mukam_recvd_no = %s
        """, (recvd_no,))
        existing = cursor.fetchone()
        if not existing:
            cursor.close()
            db.close()
            return jsonify({'status': 'error', 'message': 'Entry not found'}), 404
        if not bool(existing.get('editable', 0)):
            cursor.close()
            db.close()
            return jsonify({
                'status': 'error',
                'message': f'This entry can no longer be edited '
                           f'(allowed only within {EDIT_WINDOW_MINUTES} minutes of entry).',
            }), 403

        p = _row_payload(data, updated_by)
        upd = db.cursor()
        upd.execute("""
            UPDATE jute_mukam_recvd SET
                recvd_date = %s,
                party_id = %s,
                mukam_id = %s,
                gross_weight = %s,
                tare_weight = %s,
                `net_weight(10,3)` = %s,
                quality_id = %s,
                remarks = %s,
                updated_by = %s
            WHERE jute_mukam_recvd = %s
        """, (
            p['recvd_date'], p['party_id'], p['mukam_id'], p['gross_weight'],
            p['tare_weight'], p['net_weight'], p['quality_id'], p['remarks'],
            p['updated_by'], existing['jute_mukam_recvd'],
        ))
        db.commit()
        upd.close()
        cursor.close()
        db.close()
        return jsonify({
            'status': 'success',
            'message': 'Updated successfully',
            'jute_mukam_recvd_no': recvd_no,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
