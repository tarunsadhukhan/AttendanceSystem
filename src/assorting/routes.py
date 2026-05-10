"""
Assorting blueprint route registry.
Importing this module side-effects the route registrations from assorting.py
into the shared assorting_bp Blueprint defined in __init__.py.
"""
from . import assorting  # noqa: F401  — registers @assorting_bp.route handlers
