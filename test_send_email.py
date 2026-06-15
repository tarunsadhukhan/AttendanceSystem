"""Build one branch's SPG report PDF and EMAIL it to a single address.

Verifies SMTP delivery end to end without touching the schedule or the full
tbl_whatsapp_send recipient list. Requires SMTP_* configured in .env.

Usage:
    python test_send_email.py you@example.com               # yesterday's report
    python test_send_email.py you@example.com 2026-06-11    # specific date
"""
import os
import sys
from datetime import date, datetime, timedelta

from src.spg_report import (
    fetch_jute_details, fetch_spg_quality_shift, fetch_winding_quality_shift,
    fetch_finishing_shift, fetch_drawing_summary, active_branches, build_report_pdf,
)
from src.send_email import send_document

if len(sys.argv) < 2:
    print('Usage: python test_send_email.py <to-email> [YYYY-MM-DD]')
    sys.exit(2)

to_email = sys.argv[1]
if len(sys.argv) > 2:
    report_date = datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
else:
    report_date = date.today() - timedelta(days=1)

date_str = report_date.strftime('%Y-%m-%d')
disp_date = report_date.strftime('%d-%m-%Y')
out_dir = os.path.dirname(os.path.abspath(__file__))

fn_rows, fn_gt = fetch_finishing_shift(date_str)

sent = 0
for branch_id, branch_name in active_branches():
    jt_rows, jt_gt = fetch_jute_details(date_str, branch_id)
    sp_rows, sp_gt = fetch_spg_quality_shift(date_str, branch_id)
    wd_rows, wd_gt = fetch_winding_quality_shift(date_str, branch_id)
    dr_rows, _     = fetch_drawing_summary(date_str, branch_id)
    if not jt_rows and not sp_rows and not wd_rows and not fn_rows and not dr_rows:
        print('branch %s (%s): no data on %s - skipped' % (branch_id, branch_name, date_str))
        continue

    fname = 'SPG_Summary_TEST_%s_%s.pdf' % (branch_id, date_str)
    out_path = os.path.join(out_dir, fname)
    build_report_pdf(disp_date, branch_name,
                     (jt_rows, jt_gt), (sp_rows, sp_gt), (wd_rows, wd_gt),
                     out_path, finishing=(fn_rows, fn_gt), drawing=(dr_rows, None))

    caption = 'Spinning & Winding Production Summary %s%s' % (
        disp_date, (' - ' + branch_name) if branch_name else '')
    body = '%s\n\nPlease find the attached report.' % caption
    ok, info = send_document(to_email, out_path, subject=caption, body=body, filename=fname)
    print('branch %s (%s): email to %s -> %s | %s'
          % (branch_id, branch_name, to_email, 'OK' if ok else 'FAILED', info))
    if ok:
        sent += 1

print('done: %d email(s) sent to %s' % (sent, to_email))
