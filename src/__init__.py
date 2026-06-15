from flask import Flask, jsonify, request
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
from src.leave.leave import leave_bp
from src.doff.doff import doff_bp
from src.weight.weight import weight_bp
from src.drawing import drawing_bp
from src.spreader import spreader_bp
from src.otherentries import otherentries_bp
from src.assorting import assorting_bp
from src.jute_received import jute_received_bp
from src.jute_mukam_recvd import jute_mukam_recvd_bp
from src.balesproduction import balesproduction_bp
from src.permissions import permissions_bp


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

	@app.route('/run-spg-report', methods=['POST'])
	def run_spg_report():
		from datetime import date, datetime
		from src.spg_report import send_daily_spg_report
		d = request.args.get('date')
		try:
			report_date = datetime.strptime(d, '%Y-%m-%d').date() if d else date.today()
		except ValueError:
			return jsonify({'status': 'error', 'message': 'date must be YYYY-MM-DD'}), 400
		send_daily_spg_report(report_date)
		return jsonify({'status': 'success', 'date': report_date.isoformat()})

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
	app.register_blueprint(leave_bp)
	app.register_blueprint(doff_bp)
	app.register_blueprint(weight_bp)
	app.register_blueprint(drawing_bp)
	app.register_blueprint(spreader_bp)
	app.register_blueprint(otherentries_bp)
	app.register_blueprint(assorting_bp)
	app.register_blueprint(jute_received_bp)
	app.register_blueprint(jute_mukam_recvd_bp)
	app.register_blueprint(balesproduction_bp)
	app.register_blueprint(permissions_bp)

	return app

