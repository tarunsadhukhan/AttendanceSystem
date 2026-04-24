"""
Machine Queries Module
Contains all SQL queries related to machine operations
"""

# ══════════════════════════════════════════════════════════════════
# MACHINE MASTER QUERIES
# ══════════════════════════════════════════════════════════════════

GET_MACHINES_BY_DESIGNATION = """
    SELECT 
        mm.machine_id,
        mm.machine_name,
        mm.mech_code,
        mm.mech_shr_code,
        mm.line_no,
        mm.machine_type_id,
        mm.dept_id,
        mm.active
    FROM sjm.machine_mst mm
    LEFT JOIN sjm.mech_occu_link mol ON mm.machine_id = mol.mech_id
    WHERE mol.occu_id = %s AND mm.active = 1
    ORDER BY mm.mech_code, mm.machine_name
"""

GET_MACHINE_BY_ID = """
    SELECT 
        machine_id,
        machine_name,
        mech_code,
        mech_shr_code,
        line_no,
        machine_type_id,
        dept_id,
        active
    FROM sjm.machine_mst
    WHERE machine_id = %s AND active = 1
"""

GET_ALL_MACHINES = """
    SELECT 
        machine_id,
        machine_name,
        mech_code,
        mech_shr_code,
        line_no,
        machine_type_id,
        dept_id,
        active
    FROM sjm.machine_mst
    WHERE active = 1
    ORDER BY mech_code, machine_name
"""

# ══════════════════════════════════════════════════════════════════
# MACHINE-OCCUPATION LINK QUERIES
# ══════════════════════════════════════════════════════════════════

GET_OCCUPATIONS_FOR_MACHINE = """
    SELECT 
        mol.occu_id,
        dm.desig AS occupation_name
    FROM sjm.mech_occu_link mol
    JOIN sjm.designation_mst dm ON mol.occu_id = dm.designation_id
    WHERE mol.mech_id = %s
"""

GET_MACHINES_FOR_OCCUPATION = """
    SELECT 
        mol.mech_id,
        mm.machine_name,
        mm.mech_code
    FROM sjm.mech_occu_link mol
    JOIN sjm.machine_mst mm ON mol.mech_id = mm.machine_id
    WHERE mol.occu_id = %s AND mm.active = 1
"""

# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def format_machine_display_name(mech_code, machine_name):
    """
    Format machine display name combining code and name
    
    Args:
        mech_code: Machine code (e.g., "1001")
        machine_name: Machine name (e.g., "WINDING1001")
    
    Returns:
        Formatted display name
    """
    mech_code = mech_code or ''
    machine_name = machine_name or ''
    
    if mech_code and machine_name:
        return f"{mech_code} {machine_name}"
    elif mech_code:
        return mech_code
    elif machine_name:
        return machine_name
    else:
        return "Unknown Machine"

def build_machine_response(machine_row):
    """
    Build machine response dict from database row
    
    Args:
        machine_row: Dict from database cursor with machine data
    
    Returns:
        Dict formatted for API response
    """
    mech_code = machine_row.get('mech_code') or ''
    machine_name = machine_row.get('machine_name') or ''
    
    display_name = format_machine_display_name(mech_code, machine_name)
    
    return {
        'id': machine_row['machine_id'],
        'name': display_name,
        'mech_code': mech_code,
        'machine_no': machine_row.get('mech_shr_code') or ''
    }

