"""
Attendance Queries Module
Contains all SQL queries related to attendance operations
"""

# ══════════════════════════════════════════════════════════════════
# DAILY ATTENDANCE QUERIES
# ══════════════════════════════════════════════════════════════════

INSERT_DAILY_ATTENDANCE = """
    INSERT INTO daily_attendance (
        attendance_date, attendance_mark, attendance_source, attendance_type,
        branch_id, eb_id, entry_time, idle_hours, is_active,
        spell, spell_hours, worked_department_id, worked_designation_id,
        working_hours, update_date_time
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

UPDATE_DAILY_ATTENDANCE = """
    UPDATE daily_attendance
    SET attendance_date = %s,
        attendance_type = %s,
        worked_department_id = %s,
        worked_designation_id = %s,
        spell = %s,
        spell_hours = %s,
        working_hours = %s,
        idle_hours = %s,
        update_date_time = %s
    WHERE daily_atten_id = %s
"""

GET_ATTENDANCE_BY_ID = """
    SELECT da.daily_atten_id AS id,
           da.eb_id,
           p.emp_code,
           CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS emp_name,
           da.attendance_date,
           da.attendance_type AS att_type,
           da.attendance_source AS status,
           da.worked_department_id AS department_id,
           da.worked_designation_id AS designation_id,
           sm.spell_id AS shift_id,
           da.spell AS shift_name,
           COALESCE(da.spell_hours, 0) AS shift_hours,
           COALESCE(da.working_hours, 0) AS working_hours,
           COALESCE(da.idle_hours, 0) AS idle_hours,
           da.branch_id
    FROM daily_attendance da
    JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
    LEFT JOIN spell_mst sm ON da.spell = sm.spell_name
    WHERE da.daily_atten_id = %s AND da.is_active = 1
"""

GET_ATTENDANCE_REPORT = """
    SELECT da.daily_atten_id AS id,
           p.emp_code,
           p.eb_id,
           CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS emp_name,
           COALESCE(s.sub_dept_desc, '') AS department_name,
           COALESCE(d.desig, '') AS designation_name,
           COALESCE(da.spell, '') AS shift_name,
           da.attendance_date,
           TIME(da.entry_time) AS attendance_time,
           da.attendance_source AS status,
           da.attendance_type AS att_type,
           COALESCE(da.spell_hours, 0) AS shift_hours,
           COALESCE(da.working_hours, 0) AS working_hours,
           COALESCE(da.idle_hours, 0) AS idle_hours
    FROM daily_attendance da
    JOIN hrms_ed_personal_details p ON da.eb_id = p.eb_id
    LEFT JOIN sub_dept_mst s ON da.worked_department_id = s.sub_dept_id
    LEFT JOIN designation_mst d ON da.worked_designation_id = d.designation_id
    WHERE da.attendance_date BETWEEN %s AND %s AND da.is_active = 1
"""

# ══════════════════════════════════════════════════════════════════
# MACHINE ATTENDANCE QUERIES (daily_ebmc_attendance)
# ══════════════════════════════════════════════════════════════════

INSERT_MACHINE_ATTENDANCE = """
    INSERT INTO daily_ebmc_attendance (
        daily_atten_id, eb_id, mech_id, attendance_date, 
        branch_id, is_active, update_date_time
    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

GET_MACHINE_ATTENDANCE = """
    SELECT mm.mech_code, mm.machine_name
    FROM daily_ebmc_attendance dea
    JOIN machine_mst mm ON dea.mech_id = mm.machine_id
    WHERE dea.daily_atten_id = %s AND dea.is_active = 1
    ORDER BY mm.mech_code
"""

DELETE_MACHINE_ATTENDANCE = """
    DELETE FROM daily_ebmc_attendance 
    WHERE daily_atten_id = %s
"""

# ══════════════════════════════════════════════════════════════════
# SPELL/SHIFT QUERIES
# ══════════════════════════════════════════════════════════════════

GET_SPELL_BY_ID = """
    SELECT spell_name 
    FROM spell_mst 
    WHERE spell_id = %s
"""

GET_ALL_SPELLS = """
    SELECT spell_id, spell_name, spell_hours, spell_start, spell_end, is_active
    FROM spell_mst
    WHERE is_active = 1
    ORDER BY spell_name
"""

# ══════════════════════════════════════════════════════════════════
# HELPER QUERIES
# ══════════════════════════════════════════════════════════════════

def build_attendance_report_filters(params_dict):
    """
    Build dynamic WHERE clauses for attendance report based on filters
    
    Args:
        params_dict: Dictionary with keys: branch_id, department_id, emp_code
    
    Returns:
        Tuple of (sql_conditions, params_list)
    """
    conditions = []
    params = []
    
    if params_dict.get('branch_id'):
        conditions.append("da.branch_id = %s")
        params.append(params_dict['branch_id'])
    
    if params_dict.get('department_id'):
        conditions.append("da.worked_department_id = %s")
        params.append(params_dict['department_id'])
    
    if params_dict.get('emp_code'):
        conditions.append("p.emp_code LIKE %s")
        params.append(f"%{params_dict['emp_code']}%")
    
    if params_dict.get('shift_name'):
        conditions.append("da.spell = %s")
        params.append(params_dict['shift_name'])
    
    return (" AND " + " AND ".join(conditions)) if conditions else "", params

