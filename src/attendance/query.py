INSERT_ATTENDANCE = """
    INSERT INTO daily_attendance
      (eb_id, emp_code, attendance_date, attendance_time,
       attendance_source, att_type, photo_att,
       attendance_mark, is_active, branch_id,
       spell, spell_hours, worked_department_id, worked_designation_id,
       working_hours, idle_hours, entry_time, update_date_time)
    VALUES (%s, %s, %s, TIME(NOW()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
"""

GET_TODAY_REPORT = """
    SELECT da.emp_code,
           CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
           s.sub_dept_desc AS department,
           d.desig         AS designation,
           da.attendance_time   AS check_in,
           da.attendance_source AS status
    FROM daily_attendance da
    LEFT JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
    LEFT JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
    LEFT JOIN sub_dept_mst    s ON o.sub_dept_id    = s.sub_dept_id
    LEFT JOIN designation_mst d ON o.designation_id = d.designation_id
    WHERE da.attendance_date = CURDATE()
    ORDER BY da.attendance_time DESC
"""

GET_MONTHLY_REPORT = """
    SELECT da.emp_code,
           CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
           s.sub_dept_desc AS department,
           d.desig         AS designation,
           da.attendance_date   AS date,
           da.attendance_time   AS check_in,
           da.attendance_source AS status
    FROM daily_attendance da
    LEFT JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
    LEFT JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
    LEFT JOIN sub_dept_mst    s ON o.sub_dept_id    = s.sub_dept_id
    LEFT JOIN designation_mst d ON o.designation_id = d.designation_id
    WHERE MONTH(da.attendance_date) = %s AND YEAR(da.attendance_date) = %s
    ORDER BY da.attendance_date DESC, name
"""

GET_ATTENDANCE_REPORT_BASE = """
    SELECT da.id, da.emp_code,
           CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS emp_name,
           COALESCE(s.sub_dept_desc, '') AS department_name,
           COALESCE(d.desig, '')         AS designation_name,
           ''                            AS shift_name,
           da.attendance_date,
           da.attendance_time            AS attendance_time,
           da.attendance_source          AS status,
           da.att_type,
           COALESCE(da.shift_hours,   0) AS shift_hours,
           COALESCE(da.working_hours, 0) AS working_hours,
           COALESCE(da.idle_hours,    0) AS idle_hours,
           IF(da.photo_att IS NOT NULL, 1, 0) AS has_photo
    FROM daily_attendance da
    LEFT JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
    LEFT JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
    LEFT JOIN sub_dept_mst    s ON o.sub_dept_id    = s.sub_dept_id
    LEFT JOIN designation_mst d ON o.designation_id = d.designation_id
    WHERE da.attendance_date BETWEEN %s AND %s
"""

GET_ATTENDANCE_PHOTO = "SELECT photo_att FROM daily_attendance WHERE id = %s"

# ── Dashboard queries ─────────────────────────────────────────
COUNT_ACTIVE_EMPLOYEES = "SELECT COUNT(*) AS cnt FROM hrms_ed_personal_details WHERE active = 1"

COUNT_PRESENT_BY_DATE = """
    SELECT COUNT(DISTINCT emp_code) AS cnt
    FROM daily_attendance WHERE attendance_date = %s
"""
COUNT_PRESENT_FACE = """
    SELECT COUNT(DISTINCT emp_code) AS cnt
    FROM daily_attendance WHERE attendance_date = %s AND attendance_source = 'Face'
"""
COUNT_PRESENT_MANUAL = """
    SELECT COUNT(DISTINCT emp_code) AS cnt
    FROM daily_attendance WHERE attendance_date = %s AND attendance_source = 'Manual'
"""

GET_DEPT_EMPLOYEE_COUNT = """
    SELECT d.sub_dept_id AS department_id, d.sub_dept_desc AS department_name,
           COUNT(DISTINCT o.eb_id) AS total_employees
    FROM hrms_ed_official_details o
    JOIN sub_dept_mst d ON o.sub_dept_id = d.sub_dept_id
    GROUP BY d.sub_dept_id, d.sub_dept_desc
    ORDER BY d.sub_dept_desc
"""

GET_PRESENT_BY_DEPT = """
    SELECT o.sub_dept_id AS department_id,
           COUNT(DISTINCT da.emp_code) AS present_count
    FROM daily_attendance da
    JOIN hrms_ed_official_details o ON da.eb_id = o.eb_id
    WHERE da.attendance_date = %s
    GROUP BY o.sub_dept_id
"""
