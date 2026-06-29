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

    # Daily Hands Report (man vs machine) email. Same guard as the SPG report;
    # toggle with HANDS_REPORT_SCHEDULER=0.
    if os.getenv('HANDS_REPORT_SCHEDULER', '1') == '1' and (
            not debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            from src.send_email import start_hands_scheduler
            start_hands_scheduler()
        except Exception as ex:
            print('Hands report scheduler not started:', ex)

    # Daily Drawing Efficiency Report email. Same guard; toggle with
    # DRAWING_REPORT_SCHEDULER=0.
    if os.getenv('DRAWING_REPORT_SCHEDULER', '1') == '1' and (
            not debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            from src.send_email import start_drawing_scheduler
            start_drawing_scheduler()
        except Exception as ex:
            print('Drawing report scheduler not started:', ex)

    # Daily MIS Report email. Same guard; toggle with MIS_REPORT_SCHEDULER=0.
    if os.getenv('MIS_REPORT_SCHEDULER', '1') == '1' and (
            not debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            from src.mis_report import start_mis_scheduler
            start_mis_scheduler()
        except Exception as ex:
            print('MIS report scheduler not started:', ex)

    # Daily Summary Report (MIS01) email. Same guard; toggle with DSR_REPORT_SCHEDULER=0.
    if os.getenv('DSR_REPORT_SCHEDULER', '1') == '1' and (
            not debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            from src.daily_summary_report import start_dsr_scheduler
            start_dsr_scheduler()
        except Exception as ex:
            print('DSR report scheduler not started:', ex)

    print(f'Server ready at http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
