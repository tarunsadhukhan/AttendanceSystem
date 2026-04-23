from flask import Blueprint

masters_bp = Blueprint('masters', __name__)

from src.masters.departments import departments_bp
from src.masters.shifts       import shifts_bp
from src.masters.occupations  import occupations_bp
