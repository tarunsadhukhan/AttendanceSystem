from flask import Blueprint

spreader_bp = Blueprint('spreader', __name__, url_prefix='/spreader')

from . import routes
