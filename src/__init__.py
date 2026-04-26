from flask import Flask, jsonify
from flask_cors import CORS

from src.auth.auth import auth_bp
from src.attendance.attendance import attendance_bp
from src.config import get_config_object
from src.dashboard.dashboard import dashboard_bp
from src.dashboard.attendance_dashboard import attendance_dashboard_bp
from src.employees.employees import employees_bp
from src.masters.company_branch import company_branch_bp
from src.masters.departments import departments_bp
from src.masters.designations import designations_bp
from src.masters.machines import machines_bp
from src.masters.occupations import occupations_bp
from src.masters.shifts import shifts_bp
from src.onboarding.onboarding import onboarding_bp


def create_app(config_object=None):
	app = Flask(__name__)
	app.config.from_object(config_object or get_config_object())
	CORS(app, resources={r"/*": {"origins": app.config.get('CORS_ORIGINS', '*')}})

	@app.route('/', methods=['GET'])
	def home():
		return jsonify({
			'status': 'success',
			'message': 'Attendance Server Running!'
		})

	app.register_blueprint(auth_bp)
	app.register_blueprint(attendance_bp)
	app.register_blueprint(dashboard_bp)
	app.register_blueprint(attendance_dashboard_bp)
	app.register_blueprint(employees_bp)

	app.register_blueprint(company_branch_bp)
	app.register_blueprint(departments_bp)
	app.register_blueprint(designations_bp)
	app.register_blueprint(machines_bp)
	app.register_blueprint(occupations_bp)
	app.register_blueprint(shifts_bp)

	app.register_blueprint(onboarding_bp)

	return app

