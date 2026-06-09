from db import DB_CONFIG, init_db
from src import create_app
from src.permissions import init_permissions_db
app = create_app()
if __name__ == '__main__':
    import os
    print('Starting MyHrms Flask Server...')
    print(f"Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    init_db()
    init_permissions_db()
    port = int(os.getenv('FLASK_PORT', 5051))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # Daily Spinning Production Summary WhatsApp report (15:00/23:00 today, 07:00
    # yesterday). Start it once: in debug mode only the reloader child (the
    # process that actually serves) has WERKZEUG_RUN_MAIN=true, so we avoid a
    # duplicate scheduler in the reloader parent. Toggle with SPG_REPORT_SCHEDULER=0.
    if os.getenv('SPG_REPORT_SCHEDULER', '1') == '1' and (
            not debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            from src.spg_report import start_scheduler
            start_scheduler()
        except Exception as ex:
            print('SPG report scheduler not started:', ex)

    print(f'Server ready at http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
