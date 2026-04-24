"""
Employee Queries Module
Contains all SQL queries related to employee operations
"""

# ══════════════════════════════════════════════════════════════════
# EMPLOYEE QUERIES
# ══════════════════════════════════════════════════════════════════

GET_EMPLOYEE_BY_CODE = """
    SELECT 
        p.eb_id,
        p.emp_code,
        CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
        p.emp_photo,
        e.branch_id,
        e.dept_id AS department_id,
        e.desig_id AS designation_id,
        e.photo,
        e.is_active
    FROM hrms_ed_personal_details p
    LEFT JOIN emp_branch e ON p.eb_id = e.eb_id
    WHERE p.emp_code = %s AND e.is_active = 1
"""

GET_EMPLOYEE_WITH_BRANCH_VALIDATION = """
    SELECT 
        p.eb_id,
        p.emp_code,
        CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
        p.emp_photo,
        e.branch_id,
        e.dept_id AS department_id,
        e.desig_id AS designation_id,
        e.photo,
        e.is_active
    FROM hrms_ed_personal_details p
    LEFT JOIN emp_branch e ON p.eb_id = e.eb_id
    WHERE p.emp_code = %s AND e.branch_id = %s AND e.is_active = 1
"""

GET_ALL_EMPLOYEES = """
    SELECT 
        p.eb_id,
        p.emp_code,
        CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
        e.branch_id,
        e.dept_id AS department_id,
        e.desig_id AS designation_id,
        e.is_active
    FROM hrms_ed_personal_details p
    LEFT JOIN emp_branch e ON p.eb_id = e.eb_id
    WHERE e.is_active = 1
    ORDER BY p.emp_code
"""

SEARCH_EMPLOYEES = """
    SELECT 
        p.eb_id,
        p.emp_code,
        CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
        e.branch_id,
        e.dept_id AS department_id,
        e.desig_id AS designation_id
    FROM hrms_ed_personal_details p
    LEFT JOIN emp_branch e ON p.eb_id = e.eb_id
    WHERE (p.emp_code LIKE %s OR 
           p.first_name LIKE %s OR 
           p.middle_name LIKE %s OR 
           p.last_name LIKE %s)
    AND e.is_active = 1
    ORDER BY p.emp_code
    LIMIT 50
"""

# ══════════════════════════════════════════════════════════════════
# FACE RECOGNITION QUERIES
# ══════════════════════════════════════════════════════════════════

GET_EMPLOYEE_FACE_ENCODINGS = """
    SELECT 
        p.eb_id,
        p.emp_code,
        CONCAT(p.first_name, ' ', COALESCE(p.middle_name, ''), ' ', COALESCE(p.last_name, '')) AS name,
        e.branch_id,
        e.dept_id AS department_id,
        e.desig_id AS designation_id,
        e.photo
    FROM hrms_ed_personal_details p
    LEFT JOIN emp_branch e ON p.eb_id = e.eb_id
    WHERE e.photo IS NOT NULL 
    AND e.photo != '' 
    AND e.is_active = 1
"""

# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def format_employee_name(first_name, middle_name, last_name):
    """
    Format employee full name
    
    Args:
        first_name: Employee first name
        middle_name: Employee middle name (optional)
        last_name: Employee last name
    
    Returns:
        Formatted full name
    """
    parts = [first_name or '']
    if middle_name:
        parts.append(middle_name)
    if last_name:
        parts.append(last_name)
    return ' '.join(parts).strip()

def build_employee_response(employee_row, include_photo=False):
    """
    Build employee response dict from database row
    
    Args:
        employee_row: Dict from database cursor with employee data
        include_photo: Whether to include photo in response
    
    Returns:
        Dict formatted for API response
    """
    response = {
        'eb_id': employee_row['eb_id'],
        'emp_code': employee_row['emp_code'],
        'name': employee_row['name'].strip() if employee_row.get('name') else '',
        'branch_id': employee_row.get('branch_id'),
        'department_id': employee_row.get('department_id'),
        'designation_id': employee_row.get('designation_id'),
        'is_active': employee_row.get('is_active', 1)
    }
    
    if include_photo and employee_row.get('photo'):
        response['photo'] = employee_row['photo']
        # Convert to HTML img tag if needed
        if employee_row['photo']:
            response['photo_html'] = f"<img src='data:image/jpeg;base64,{employee_row['photo']}' />"
    
    return response

