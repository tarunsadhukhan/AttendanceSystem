from flask import Blueprint

jute_received_bp = Blueprint('jute_received', __name__, url_prefix='/jute-received')

from . import routes  # noqa: F401
