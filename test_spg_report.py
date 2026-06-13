"""Build the SPG report PDF locally WITHOUT sending WhatsApp messages.

Usage:
    python test_spg_report.py              # yesterday's report
    python test_spg_report.py 2026-06-11   # specific date
"""
import os
import sys
from datetime import date, datetime, timedelta

from src.spg_report import (
    fetch_jute_details, fetch_spg_quality_shift, fetch_winding_quality_shift,
    fetch_finishing_shift, fetch_drawing_summary, active_branches, build_report_pdf,
)

if len(sys.argv) > 1:
    report_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
else:
    report_date = date.today() - timedelta(days=1)

date_str = report_date.strftime('%Y-%m-%d')
disp_date = report_date.strftime('%d-%m-%Y')
out_dir = os.path.dirname(os.path.abspath(__file__))

fn_rows, fn_gt = fetch_finishing_shift(date_str)

built = 0
for branch_id, branch_name in active_branches():
    jt_rows, jt_gt = fetch_jute_details(date_str, branch_id)
    sp_rows, sp_gt = fetch_spg_quality_shift(date_str, branch_id)
    wd_rows, wd_gt = fetch_winding_quality_shift(date_str, branch_id)
    dr_rows, _     = fetch_drawing_summary(date_str, branch_id)
    if not jt_rows and not sp_rows and not wd_rows and not fn_rows and not dr_rows:
        print('branch %s (%s): no data on %s - skipped' % (branch_id, branch_name, date_str))
        continue
    out_path = os.path.join(out_dir, 'SPG_Summary_TEST_%s_%s.pdf' % (branch_id, date_str))
    build_report_pdf(disp_date, branch_name,
                     (jt_rows, jt_gt), (sp_rows, sp_gt), (wd_rows, wd_gt),
                     out_path, finishing=(fn_rows, fn_gt), drawing=(dr_rows, None))
    print('branch %s (%s): built %s  (jute=%d, spg=%d, wdg=%d, other=%d, draw=%d rows)'
          % (branch_id, branch_name, out_path, len(jt_rows), len(sp_rows),
             len(wd_rows), len(fn_rows), len(dr_rows)))
    built += 1

print('done: %d PDF(s) built, nothing sent' % built)
