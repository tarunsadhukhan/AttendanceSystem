from flask import Flask, jsonify
from flask_cors import CORS
from db import init_db

from src.masters.departments  import departments_bp
from src.masters.shifts       import shifts_bp
from src.masters.occupations  import occupations_bp
from src.masters.designations import designations_bp
from src.employees.employees  import employees_bp
from src.attendance.attendance import attendance_bp
from src.auth.auth            import auth_bp
from src.masters.company_branch import company_branch_bp
from src.dashboard.dashboard  import dashboard_bp
from src.onboarding.onboarding import onboarding_bp
from src.masters.machines      import machines_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(departments_bp)
app.register_blueprint(shifts_bp)
app.register_blueprint(occupations_bp)
app.register_blueprint(designations_bp)
app.register_blueprint(employees_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(company_branch_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(machines_bp)


# ── Health check ─────────────────────────────────────────────
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "success",
                    "message": "✅ Attendance Server Running!"})


# ── Init DB (for gunicorn) ────────────────────────────────────
try:
    init_db()
except Exception as e:
    print(f"⚠️ init_db failed (will retry on first request): {e}")


if __name__ == '__main__':
    print("[OK] Starting Attendance Server...")
    print("[OK] Open http://localhost:5051 to verify")
    app.run(debug=True, host='0.0.0.0', port=5051, use_reloader=True)
