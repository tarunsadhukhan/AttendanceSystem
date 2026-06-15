from flask import Blueprint

jute_mukam_recvd_bp = Blueprint('jute_mukam_recvd', __name__, url_prefix='/jute-mukam-recvd')

from . import routes  # noqa: F401
