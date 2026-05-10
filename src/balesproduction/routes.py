"""
Bales Production blueprint route registry.
Importing this module side-effects the route registrations from balesproduction.py
into the shared balesproduction_bp Blueprint defined in __init__.py.
"""
from . import balesproduction  # noqa: F401  — registers @balesproduction_bp.route handlers