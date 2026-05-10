from flask import Blueprint

otherentries_bp = Blueprint('otherentries', __name__, url_prefix='/otherentries')

from . import otherentries  # noqa: F401
