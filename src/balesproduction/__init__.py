from flask import Blueprint

balesproduction_bp = Blueprint('balesproduction', __name__, url_prefix='/balesproduction')

from . import routes