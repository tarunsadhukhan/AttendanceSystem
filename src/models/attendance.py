from dataclasses import dataclass
from typing import Optional


@dataclass
class Attendance:
    employee_id: int
    emp_code: str
    date: str                            # YYYY-MM-DD
    shift_id: Optional[int]       = None
    department_id: Optional[int]  = None
    designation_id: Optional[int] = None
    status: str                   = 'Face'   # 'Face' | 'Manual'
    att_type: str                 = 'R'      # R=Regular, O=OT, C=Cash
    photo_att: Optional[str]      = None
    shift_hours: float            = 0.0
    working_hours: float          = 0.0
    idle_hours: float             = 0.0
    id: Optional[int]             = None
    check_in: Optional[str]       = None
    check_out: Optional[str]      = None
