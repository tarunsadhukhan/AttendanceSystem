"""
Jute Mukam Received blueprint route registry.
Importing this module side-effects the route registrations from
jute_mukam_recvd.py into the shared jute_mukam_recvd_bp Blueprint.
"""
from . import jute_mukam_recvd  # noqa: F401  — registers @jute_mukam_recvd_bp.route handlers
