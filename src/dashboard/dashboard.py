import traceback
from flask import Blueprint, request, jsonify
from datetime import datetime
from db import get_db

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard-stats', methods=['GET'])
def dashboard_stats():
    """
    Returns dashboard statistics for a given date.
    Query params:
      - date      (yyyy-MM-dd) — defaults to today
      - branch_id (int)        — filter by branch
      - co_id     (int)        — filter by company
    """
    try:
        stat_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        branch_id = request.args.get('branch_id', type=int)
        co_id     = request.args.get('co_id', type=int)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # ── Total departments (sub_dept_mst) ─────────────────────
        if branch_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM sub_dept_mst sdm
                LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
                WHERE dm.branch_id = %s
            """, (branch_id,))
        elif co_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM sub_dept_mst sdm
                LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
                WHERE dm.co_id = %s
            """, (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM sub_dept_mst")
        total_departments = cursor.fetchone()['cnt']

        # ── Total designations ───────────────────────────────────
        if branch_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM designation_mst WHERE active = 1 AND branch_id = %s",
                (branch_id,))
        elif co_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM designation_mst WHERE active = 1 AND co_id = %s",
                (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM designation_mst WHERE active = 1")
        total_designations = cursor.fetchone()['cnt']

        # ── Total shifts ─────────────────────────────────────────
        if branch_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM shift_mst WHERE branch_id = %s",
                (branch_id,))
        elif co_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM shift_mst WHERE co_id = %s",
                (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM shift_mst")
        total_shifts = cursor.fetchone()['cnt']

        # ── Total employees (hrms_ed_official_details) ───────────
        if branch_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE branch_id = %s",
                (branch_id,))
        elif co_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE co_id = %s",
                (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM hrms_ed_official_details")
        total_employees = cursor.fetchone()['cnt']

        # ── Present (daily_attendance) ───────────────────────────
        if branch_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM daily_attendance da
                WHERE da.attendance_date = %s AND da.branch_id = %s
            """, (stat_date, branch_id))
        elif co_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM daily_attendance da
                JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
                WHERE da.attendance_date = %s AND o.co_id = %s
            """, (stat_date, co_id))
        else:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM daily_attendance WHERE attendance_date = %s",
                (stat_date,))
        total_present = cursor.fetchone()['cnt']

        # ── Present by Face ──────────────────────────────────────
        if branch_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM daily_attendance da
                WHERE da.attendance_date = %s AND da.attendance_source = 'Face'
                  AND da.branch_id = %s
            """, (stat_date, branch_id))
        elif co_id:
            cursor.execute("""
                                SELECT COUNT(*) AS cnt
                                FROM daily_attendance da
                                JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
                                WHERE da.attendance_date = %s AND da.attendance_source = 'Face'
                                    AND o.co_id = %s
            """, (stat_date, co_id))
        else:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM daily_attendance
                WHERE attendance_date = %s AND attendance_source = 'Face'
            """, (stat_date,))
        present_face = cursor.fetchone()['cnt']

        # ── Present by Manual ────────────────────────────────────
        if branch_id:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM daily_attendance da
                WHERE da.attendance_date = %s AND da.attendance_source = 'Manual'
                  AND da.branch_id = %s
            """, (stat_date, branch_id))
        elif co_id:
            cursor.execute("""
                                SELECT COUNT(*) AS cnt
                                FROM daily_attendance da
                                JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
                                WHERE da.attendance_date = %s AND da.attendance_source = 'Manual'
                                    AND o.co_id = %s
            """, (stat_date, co_id))
        else:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM daily_attendance
                WHERE attendance_date = %s AND attendance_source = 'Manual'
            """, (stat_date,))
        present_manual = cursor.fetchone()['cnt']

        # ── Absent ───────────────────────────────────────────────
        total_absent = max(0, total_employees - total_present)

        # ── Department-wise stats ────────────────────────────────
        # Employee counts per sub-department
        emp_dept_query = """
            SELECT sdm.sub_dept_id AS department_id,
                   sdm.sub_dept_desc AS department_name,
                   COUNT(o.eb_id) AS total_employees
            FROM sub_dept_mst sdm
            LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
            LEFT JOIN hrms_ed_official_details o ON sdm.sub_dept_id = o.sub_dept_id
        """
        emp_params = []
        if branch_id:
            emp_dept_query += " WHERE dm.branch_id = %s"
            emp_params.append(branch_id)
        elif co_id:
            emp_dept_query += " WHERE dm.co_id = %s"
            emp_params.append(co_id)
        emp_dept_query += " GROUP BY sdm.sub_dept_id, sdm.sub_dept_desc ORDER BY sdm.sub_dept_desc"
        cursor.execute(emp_dept_query, tuple(emp_params) if emp_params else ())
        dept_stats = cursor.fetchall()

        # Present counts per sub-department — join through hrms_ed_official_details
        # because daily_attendance has no sub_dept_id column
        pres_dept_query = """
            SELECT o.sub_dept_id AS department_id, COUNT(*) AS present_count
            FROM daily_attendance da
            JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
            WHERE da.attendance_date = %s
        """
        pres_params = [stat_date]
        if branch_id:
            pres_dept_query += " AND da.branch_id = %s"
            pres_params.append(branch_id)
        elif co_id:
            pres_dept_query += " AND o.co_id = %s"
            pres_params.append(co_id)
        pres_dept_query += " GROUP BY o.sub_dept_id"
        cursor.execute(pres_dept_query, tuple(pres_params))
        present_by_dept = {row['department_id']: row['present_count']
                           for row in cursor.fetchall()}

        department_wise = []
        for dept in dept_stats:
            present_count = present_by_dept.get(dept['department_id'], 0)
            total_emp = dept['total_employees']
            department_wise.append({
                'department_id':   dept['department_id'],
                'department_name': dept['department_name'],
                'total_employees': total_emp,
                'present':         present_count,
                'absent':          max(0, total_emp - present_count)
            })

        cursor.close()
        db.close()

        return jsonify({
            'status':             'success',
            'date':               stat_date,
            'total_departments':  total_departments,
            'total_designations': total_designations,
            'total_shifts':       total_shifts,
            'total_employees':    total_employees,
            'total_present':      total_present,
            'present_face':       present_face,
            'present_manual':     present_manual,
            'total_absent':       total_absent,
            'department_wise':    department_wise
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

