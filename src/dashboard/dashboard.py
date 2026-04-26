import traceback
from datetime import datetime

from flask import Blueprint, jsonify, request

from db import get_db


dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard-stats', methods=['GET'])
def dashboard_stats():
    """
    Returns dashboard statistics for a given date.
    Query params:
      - date      (yyyy-MM-dd) - defaults to today
      - branch_id (int)        - filter by branch
      - co_id     (int)        - filter by company
    """
    try:
        stat_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        branch_id = request.args.get('branch_id', type=int)
        co_id = request.args.get('co_id', type=int)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        if branch_id:
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM sub_dept_mst sdm
                LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
                WHERE dm.branch_id = %s
                """,
                (branch_id,),
            )
        elif co_id:
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM sub_dept_mst sdm
                LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
                WHERE dm.co_id = %s
                """,
                (co_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM sub_dept_mst")
        total_departments = cursor.fetchone()["cnt"]

        if branch_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM designation_mst WHERE active = 1 AND branch_id = %s",
                (branch_id,),
            )
        elif co_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM designation_mst WHERE active = 1 AND co_id = %s",
                (co_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM designation_mst WHERE active = 1")
        total_designations = cursor.fetchone()["cnt"]

        if branch_id:
            cursor.execute("SELECT COUNT(*) AS cnt FROM shift_mst WHERE branch_id = %s", (branch_id,))
        elif co_id:
            cursor.execute("SELECT COUNT(*) AS cnt FROM shift_mst WHERE co_id = %s", (co_id,))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM shift_mst")
        total_shifts = cursor.fetchone()["cnt"]

        if branch_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE branch_id = %s",
                (branch_id,),
            )
        elif co_id:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM hrms_ed_official_details WHERE co_id = %s",
                (co_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM hrms_ed_official_details")
        total_employees = cursor.fetchone()["cnt"]

        if branch_id:
            cursor.execute(
                """
                SELECT COUNT( da.eb_id) AS cnt
                FROM daily_attendance da
                WHERE da.attendance_date = %s AND da.branch_id = %s
                """,
                (stat_date, branch_id),
            )
        elif co_id:
            cursor.execute(
                """
                SELECT COUNT(da.eb_id) AS cnt
                FROM daily_attendance da
                JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
                WHERE da.attendance_date = %s AND o.co_id = %s
                """,
                (stat_date, co_id),
            )
        else:
            cursor.execute(
                "SELECT COUNT( eb_id) AS cnt FROM daily_attendance WHERE attendance_date = %s",
                (stat_date,),
            )
        total_present = cursor.fetchone()["cnt"]

        if branch_id:
            cursor.execute(
                """
                SELECT COUNT( da.eb_id) AS cnt
                FROM daily_attendance da
                WHERE da.attendance_date = %s
                  AND da.attendance_source IN ( 'Face','BIO')
                  AND da.branch_id = %s
                """,
                (stat_date, branch_id),
            )
        elif co_id:
            cursor.execute(
                """
                SELECT COUNT( da.eb_id) AS cnt
                FROM daily_attendance da
                JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
                WHERE da.attendance_date = %s
                  AND da.attendance_source IN ( 'Face','BIO')
                  AND o.co_id = %s
                """,
                (stat_date, co_id),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT( eb_id) AS cnt
                FROM daily_attendance
                WHERE attendance_date = %s AND attendance_source IN ( 'Face','BIO')
                """,
                (stat_date,),
            )
        present_face = cursor.fetchone()["cnt"]

        if branch_id:
            cursor.execute(
                """
                SELECT COUNT( da.eb_id) AS cnt
                FROM daily_attendance da
                WHERE da.attendance_date = %s
                  AND da.attendance_source = 'Manual'
                  AND da.branch_id = %s
                """,
                (stat_date, branch_id),
            )
        elif co_id:
            cursor.execute(
                """
                SELECT COUNT( da.eb_id) AS cnt
                FROM daily_attendance da
                JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
                WHERE da.attendance_date = %s
                  AND da.attendance_source = 'Manual'
                  AND o.co_id = %s
                """,
                (stat_date, co_id),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT( eb_id) AS cnt
                FROM daily_attendance
                WHERE attendance_date = %s AND attendance_source = 'Manual'
                """,
                (stat_date,),
            )
        present_manual = cursor.fetchone()["cnt"]

        # Query for all departments (master list)
        master_query = """
            	SELECT sdm.sub_dept_id AS department_id,
                   sdm.sub_dept_desc AS department_name,
                   0  AS total_employees,
                   COUNT( da.eb_id) AS present
            FROM sub_dept_mst sdm
            LEFT JOIN dept_mst dm ON dm.dept_id = sdm.dept_id
            LEFT JOIN daily_attendance da
              ON da.worked_department_id  = sdm.sub_dept_id 
             AND da.attendance_date = %s
             AND da.is_active = 1
    
        """
        master_params = [stat_date]

        if branch_id:
            master_query += " WHERE dm.branch_id = %s"
            master_params.append(branch_id)
        elif co_id:
            master_query += " WHERE dm.co_id = %s"
            master_params.append(co_id)

        master_query += """
            GROUP BY sdm.sub_dept_id, sdm.sub_dept_desc
            ORDER BY sdm.sub_dept_desc
        """
        print(f"Executing master query: {master_query} with params {master_params}")
        cursor.execute(master_query, tuple(master_params))
        all_depts = cursor.fetchall()

        # Build department_present (only departments with present > 0)
        department_present = []
        department_master = []
        
        for dept in all_depts:
            total_emp = dept["total_employees"] or 0
            present_count = dept["present"] or 0
            
            dept_data = {
                "department_id": dept["department_id"],
                "department_name": dept["department_name"],
                "total_employees": total_emp,
                "present": present_count,
                "absent": max(0, total_emp - present_count),
            }
            
            # Add to master list
            department_master.append(dept_data)
            
            # Add to present list only if has present employees
            if present_count > 0:
                department_present.append(dept_data.copy())

        # Preserve the existing response contract key.
        department_wise = department_present

        total_absent = max(0, total_employees - total_present)
        cursor.close()
        db.close()
        #print(f"Total Employees: {total_employees}, Total Present: {total_present}, Total Absent: {total_absent}")
        print(f"Department-wise: {department_wise}")
        return jsonify(
            {
                "status": "success",
                "date": stat_date,
                "total_departments": total_departments,
                "total_designations": total_designations,
                "total_shifts": total_shifts,
                "total_employees": total_employees,
                "total_present": total_present,
                "present_face": present_face,
                "present_manual": present_manual,
                "total_absent": total_absent,
                "department_wise": department_wise,
                "department_present": department_present,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
