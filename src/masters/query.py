# ── Departments ──────────────────────────────────────────────
GET_ALL_DEPARTMENTS = "SELECT sub_dept_id AS id, sub_dept_desc AS name FROM sub_dept_mst ORDER BY sub_dept_desc"

GET_DEPARTMENTS_BY_BRANCH = """
    SELECT DISTINCT s.sub_dept_id AS id, s.sub_dept_desc AS name
    FROM sub_dept_mst s
    JOIN dept_mst d ON s.dept_id = d.dept_id
    WHERE d.branch_id = %s
    ORDER BY s.sub_dept_desc
"""

GET_DEPARTMENTS_BY_COMPANY_BRANCH = """
    SELECT DISTINCT s.sub_dept_id AS id, s.sub_dept_desc AS name
    FROM sub_dept_mst s
    JOIN dept_mst d ON s.dept_id = d.dept_id
    JOIN branch_mst b ON d.branch_id = b.branch_id
    WHERE b.co_id = %s AND d.branch_id = %s
    ORDER BY s.sub_dept_desc
"""

GET_DEPARTMENTS_BY_COMPANY = """
    SELECT DISTINCT s.sub_dept_id AS id, s.sub_dept_desc AS name
    FROM sub_dept_mst s
    JOIN dept_mst d ON s.dept_id = d.dept_id
    JOIN branch_mst b ON d.branch_id = b.branch_id
    WHERE b.co_id = %s
    ORDER BY s.sub_dept_desc
"""

GET_DEPT_BY_NAME    = "SELECT sub_dept_id AS id FROM sub_dept_mst WHERE sub_dept_desc = %s"
INSERT_DEPARTMENT   = "INSERT INTO sub_dept_mst (sub_dept_desc) VALUES (%s)"
UPDATE_DEPARTMENT   = "UPDATE sub_dept_mst SET sub_dept_desc = %s WHERE sub_dept_id = %s"
DELETE_DEPARTMENT   = "DELETE FROM sub_dept_mst WHERE sub_dept_id = %s"

# Designations (from designation_mst)
GET_DESIGNATIONS_BY_BRANCH = """
    SELECT designation_id AS id, desig AS name
    FROM designation_mst
    WHERE branch_id = %s AND active = 1
    ORDER BY desig
"""

GET_DESIGNATIONS_BY_DEPT_BRANCH = """
    SELECT DISTINCT dm.designation_id AS id, dm.desig AS name
    FROM designation_mst dm
    JOIN sub_dept_mst s ON dm.dept_id = s.dept_id
    WHERE s.sub_dept_id = %s AND dm.branch_id = %s AND dm.active = 1
    ORDER BY dm.desig
"""

# ── Shifts ────────────────────────────────────────────────────
GET_ALL_SHIFTS    = "SELECT id, name, start_time, end_time FROM shifts ORDER BY start_time"
GET_SHIFT_BY_NAME = "SELECT id FROM shifts WHERE name = %s"
INSERT_SHIFT      = "INSERT INTO shifts (name, start_time, end_time) VALUES (%s, %s, %s)"
UPDATE_SHIFT      = "UPDATE shifts SET name = %s, start_time = %s, end_time = %s WHERE id = %s"
DELETE_SHIFT      = "DELETE FROM shifts WHERE id = %s"

# ── Occupations ───────────────────────────────────────────────
GET_ALL_OCCUPATIONS = "SELECT id, name, created_at FROM occupations ORDER BY name"
GET_OCC_BY_NAME     = "SELECT id FROM occupations WHERE name = %s"
INSERT_OCCUPATION   = "INSERT INTO occupations (name) VALUES (%s)"
UPDATE_OCCUPATION   = "UPDATE occupations SET name = %s WHERE id = %s"
DELETE_OCCUPATION   = "DELETE FROM occupations WHERE id = %s"

# ── Companies / Branches (SLS masters) ─────────────────────────────
GET_ALL_COMPANIES = """
    SELECT
        co_id,
        co_name,
        co_logo
    FROM co_mst cm where cm.co_id<=2
    ORDER BY co_name
"""



GET_BRANCHES_BY_COMPANY = """
    SELECT
        branch_id AS br_id,
        co_id,
        branch_name AS br_name
    FROM branch_mst
    WHERE co_id = %s
    ORDER BY branch_name
"""
