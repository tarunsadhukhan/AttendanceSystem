"""
Jute Received blueprint route registry.
Importing this module side-effects the route registrations from jute_received.py
into the shared jute_received_bp Blueprint defined in __init__.py.
"""
from . import jute_received  # noqa: F401  — registers @jute_received_bp.route handlers
