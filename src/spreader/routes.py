"""
Spreader blueprint route registry.
Importing this module side-effects the route registrations from spreader.py
into the shared spreader_bp Blueprint defined in __init__.py.
"""
from . import spreader  # noqa: F401  — registers @spreader_bp.route handlers