"""Self-check for face-attendance spell window validation. Run: python test_spell_window.py"""
from datetime import datetime, timedelta
from src.attendance.attendance import _spell_window_error as err

A = {'spell_name': 'A', 'starting_time': timedelta(hours=6),  'end_time': timedelta(hours=14), 'is_overnight': 0}
C = {'spell_name': 'C', 'starting_time': timedelta(hours=22), 'end_time': timedelta(hours=6),  'is_overnight': 1}
D = '2026-08-28'

# Spell A: 06:00-14:00 same day
assert err(D, A, datetime(2026, 8, 28, 6, 0))   is None
assert err(D, A, datetime(2026, 8, 28, 13, 59)) is None
assert err(D, A, datetime(2026, 8, 28, 14, 1))  is not None   # after spell
assert err(D, A, datetime(2026, 8, 28, 5, 59))  is not None   # before spell
assert err(D, A, datetime(2026, 8, 29, 8, 0))   is not None   # wrong date

# Spell C overnight: 28th 22:00 -> 29th 06:00
assert err(D, C, datetime(2026, 8, 28, 22, 0))  is None
assert err(D, C, datetime(2026, 8, 29, 5, 59))  is None
assert err(D, C, datetime(2026, 8, 29, 6, 1))   is not None
assert err(D, C, datetime(2026, 8, 28, 21, 0))  is not None
assert err(D, C, datetime(2026, 8, 27, 23, 0))  is not None   # previous night, wrong date

# No spell / no times -> skip validation
assert err(D, None) is None
assert err(D, {'spell_name': 'X', 'starting_time': None, 'end_time': None}) is None

print("OK")
