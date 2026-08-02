from dataclasses import dataclass
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


@dataclass
class DrawingMst:
    """tbl_drawing_mst — Drawing machine master."""
    drg_mst_id: int
    mc_id: int
    short_name: Optional[str]       # Display name e.g. "Drg 1 (OS)"
    shed_type: Optional[str]        # e.g. "Old Shed"
    const_meter: Optional[int]      # Efficiency constant (meter/hour baseline)
    drg_type: Optional[int]
    branch_id: Optional[int]
    updated_by: Optional[int]
    updated_date_time: Optional[datetime]
    meter_type: int = 1             # 0=hide meter-units boxes, 1=as-is, 2=/3600

    @staticmethod
    def from_row(row: dict) -> 'DrawingMst':
        return DrawingMst(
            drg_mst_id=row['drg_mst_id'],
            mc_id=row['mc_id'],
            short_name=row.get('short_name'),
            shed_type=row.get('shed_type'),
            const_meter=row.get('const_meter'),
            drg_type=row.get('drg_type'),
            branch_id=row.get('branch_id'),
            updated_by=row.get('updated_by'),
            updated_date_time=row.get('updated_date_time'),
            meter_type=row.get('meter_type', 1) if row.get('meter_type') is not None else 1,
        )

    def to_dict(self) -> dict:
        return {
            'drg_mst_id': self.drg_mst_id,
            'mc_id': self.mc_id,
            'short_name': self.short_name,
            'shed_type': self.shed_type,
            'const_meter': self.const_meter,
            'drg_type': self.drg_type,
            'branch_id': self.branch_id,
            'meter_type': self.meter_type,
        }


@dataclass
class DailyDrawing:
    """tbl_daily_drawing — Daily drawing meter entry."""
    tbl_daily_drg_id: Optional[int]
    mc_id: int
    tran_date: date
    spell_id: int
    opening_meter: Optional[int]
    closing_meter: Optional[int]
    difference: Optional[int]       # closing_meter - opening_meter
    unit: Optional[int]       # closing_meter - opening_meter
    const_meter: Optional[int]      # Copy from master at save time
    running_hours: Optional[Decimal]
    branch_id: Optional[int]
    updated_by: Optional[int]
    updated_date_time: Optional[datetime]
    meter_units: Optional[Decimal] = None   # raw input
    meter_hours: Optional[Decimal] = None   # calculated per master meter_type

    @property
    def eff(self) -> Optional[float]:
        """Calculate efficiency on the fly (not stored in DB)."""
        try:
            if self.running_hours and float(self.running_hours) > 0 and self.const_meter:
                return round(
                    ((self.difference / float(self.running_hours) * 8) / self.const_meter * 100),
                    2
                )
        except (TypeError, ZeroDivisionError):
            pass
        return 0.0

    @property
    def meter_eff(self) -> float:
        """meter_hours / running_hours * 100 (not stored in DB)."""
        try:
            if self.running_hours and float(self.running_hours) > 0 and self.meter_hours is not None:
                return round(float(self.meter_hours) / float(self.running_hours) * 100, 2)
        except (TypeError, ZeroDivisionError):
            pass
        return 0.0

    @staticmethod
    def from_row(row: dict) -> 'DailyDrawing':
        return DailyDrawing(
            tbl_daily_drg_id=row.get('tbl_daily_drg_id'),
            mc_id=row['mc_id'],
            tran_date=row['tran_date'],
            spell_id=row['spell_id'],
            opening_meter=row.get('opening_meter'),
            closing_meter=row.get('closing_meter'),
            difference=row.get('difference'),
            unit=row.get('unit'),
            const_meter=row.get('const_meter'),
            running_hours=row.get('running_hours'),
            branch_id=row.get('branch_id'),
            updated_by=row.get('updated_by'),
            updated_date_time=row.get('updated_date_time'),
            meter_units=row.get('meter_units'),
            meter_hours=row.get('meter_hours'),
        )

    def to_dict(self) -> dict:
        return {
            'id': self.tbl_daily_drg_id,
            'mc_id': self.mc_id,
            'tran_date': str(self.tran_date) if self.tran_date else None,
            'spell_id': self.spell_id,
            'opening_meter': self.opening_meter,
            'closing_meter': self.closing_meter,
            'difference': self.difference,
            'unit': self.unit,
            'const_meter': self.const_meter,
            'running_hours': float(self.running_hours) if self.running_hours is not None else None,
            'meter_units': float(self.meter_units) if self.meter_units is not None else 0.0,
            'meter_hours': float(self.meter_hours) if self.meter_hours is not None else 0.0,
            'meter_eff': self.meter_eff,
            'eff': self.eff,
            'branch_id': self.branch_id,
        }
