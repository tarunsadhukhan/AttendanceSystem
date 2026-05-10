from flask import Blueprint

assorting_bp = Blueprint('assorting', __name__, url_prefix='/assorting')

from . import routes  # noqa: F401
