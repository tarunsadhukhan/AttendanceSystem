import os

from db import DB_CONFIG, init_db
from src import create_app
from src.permissions import init_permissions_db

app = create_app()

# (env toggle, module, start function) for the five report schedulers.
_SCHEDULERS = [
    ('SPG_REPORT_SCHEDULER',     'src.spg_report',           'start_scheduler'),
    ('HANDS_REPORT_SCHEDULER',   'src.send_email',           'start_hands_scheduler'),
    ('DRAWING_REPORT_SCHEDULER', 'src.send_email',           'start_drawing_scheduler'),
    ('MIS_REPORT_SCHEDULER',     'src.mis_report',           'start_mis_scheduler'),
    ('DSR_REPORT_SCHEDULER',     'src.daily_summary_report', 'start_dsr_scheduler'),
]


def start_background(debug=False):
    """DB init + report schedulers.

    Called from __main__ for local dev, or at import time when
    RUN_SCHEDULERS=1 (gunicorn/Docker — run gunicorn with exactly 1 worker
    or every worker starts its own schedulers and jobs double-fire).
    Under the Flask debug reloader only the serving child (the process with
    WERKZEUG_RUN_MAIN=true) starts the schedulers, so the reloader parent
    doesn't duplicate them.
    """
    import importlib

    init_db()
    init_permissions_db()
    for env_var, module, func in _SCHEDULERS:
        if os.getenv(env_var, '1') != '1':
            continue
        if debug and os.getenv('WERKZEUG_RUN_MAIN') != 'true':
            continue
        try:
            getattr(importlib.import_module(module), func)()
        except Exception as ex:
            print(f'{func} not started:', ex)


if os.getenv('RUN_SCHEDULERS') == '1':
    start_background()

if __name__ == '__main__':
    print('Starting MyHrms Flask Server...')
    print(f"Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    port = int(os.getenv('FLASK_PORT', 5051))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    start_background(debug)
    print(f'Server ready at http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
