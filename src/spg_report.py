"""Daily Spinning Production Summary — PDF report sent over WhatsApp.

Sends a per-branch "Spinning Production Summary" PDF (quality x shift A/B/C
totals) to WhatsApp recipients in tbl_whatsapp_send where msg_for='SR'.

Schedule (server local time):
  - 15:00  -> report for the current date
  - 23:00  -> report for the current date
  - 07:00  -> report for the PREVIOUS date (current date - 1 day)

The 07:00 run covers the day that just ended, e.g. on 08-06-2026 at 07:00 it
sends the 07-06-2026 report.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

from fpdf import FPDF

from db import get_db
from src.send_whatsapp import send_document


# -- data ---------------------------------------------------------------------

def fetch_spg_quality_shift(date_str, branch_id):
    """Return (rows, grand_total) for the spinning quality/shift summary.

    rows: [{quality_name, shift_a, shift_b, shift_c, total}, ...]
    grand_total: {shift_a, shift_b, shift_c, total}
    This is the same query backing GET /doff/spg1-quality-shift-report.
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    sql = """
        SELECT
            COALESCE(concat(spg_type_name,' ',q.spg_quality,' ',q.speed,' RPM') , 'Unknown') AS quality_name,
            COALESCE(SUM(CASE WHEN s.spell_name LIKE '%A%' THEN d.net_weight ELSE 0 END), 0) AS shift_a,
            COALESCE(SUM(CASE WHEN s.spell_name LIKE '%B%' THEN d.net_weight ELSE 0 END), 0) AS shift_b,
            COALESCE(SUM(CASE WHEN s.spell_name LIKE '%C%' THEN d.net_weight ELSE 0 END), 0) AS shift_c,
            COALESCE(SUM(d.net_weight), 0) AS total
        FROM daily_doff_tbl d
        LEFT JOIN spell_mst s ON d.spell = s.spell_id
        left join daily_doff_frames_winding ddfw on ddfw.tran_date =d.doff_date and ddfw.spell =d.spell
        and ddfw.mc_eb_id =d.mc_id and ddfw.active =1 and spg_wdg='S'
        LEFT JOIN spinning_quality_mst q ON ddfw.quality_id = q.spg_quality_mst_id
        left join spinning_type_mst stm on stm.spg_type_mst_id =q.spg_type_id
        WHERE d.doff_date = %s AND d.branch_id = %s
          AND (d.active IS NULL OR d.active = 1)
        GROUP BY concat(spg_type_name,' ',q.spg_quality,' ',q.speed)
        ORDER BY concat(spg_type_name,' ',q.spg_quality,' ',q.speed)
    """
    cur.execute(sql, (date_str, branch_id))
    rows = cur.fetchall()
    cur.close(); db.close()
    return rows, _grand_total(rows)


def fetch_winding_quality_shift(date_str, branch_id):
    """Return (rows, grand_total) for the winding quality/shift summary.

    Same shape as fetch_spg_quality_shift; backs
    GET /doff/winding-entry-2-quality-shift-report.
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    sql = """
        SELECT
            COALESCE(q.wng_quality, 'Unknown') AS quality_name,
            COALESCE(SUM(CASE WHEN s.spell_name LIKE '%A%' THEN w.net_weight ELSE 0 END), 0) AS shift_a,
            COALESCE(SUM(CASE WHEN s.spell_name LIKE '%B%' THEN w.net_weight ELSE 0 END), 0) AS shift_b,
            COALESCE(SUM(CASE WHEN s.spell_name LIKE '%C%' THEN w.net_weight ELSE 0 END), 0) AS shift_c,
            COALESCE(SUM(w.net_weight), 0) AS total
        FROM daily_doff_frames_winding w
        left join daily_doff_frames_winding ddfw on ddfw.mc_eb_id =w.eb_id and ddfw.tran_date =w.tran_date
        and ddfw.spell =w.spell and ddfw.eb_id is null
        LEFT JOIN spell_mst s ON w.spell_id = s.spell_id
        LEFT JOIN winding_quality_master q ON ddfw.quality_id = q.wng_quality_mst_id
        WHERE w.tran_date = %s
          AND w.branch_id = %s
          AND w.spg_wdg = 'W'
          AND w.net_weight IS NOT NULL
          AND (w.active IS NULL OR w.active = 1)
        GROUP BY q.wng_quality
        ORDER BY q.wng_quality
    """
    cur.execute(sql, (date_str, branch_id))
    rows = cur.fetchall()
    cur.close(); db.close()
    return rows, _grand_total(rows)


def _grand_total(rows):
    return {
        'shift_a': sum(float(r['shift_a'] or 0) for r in rows),
        'shift_b': sum(float(r['shift_b'] or 0) for r in rows),
        'shift_c': sum(float(r['shift_c'] or 0) for r in rows),
        'total':   sum(float(r['total']   or 0) for r in rows),
    }


def active_branches():
    """Return [(branch_id, branch_name), ...] for active branches."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT branch_id, branch_name
        FROM branch_mst
        WHERE (active IS NULL OR active = 1)
        ORDER BY branch_id
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    return [(r['branch_id'], (r.get('branch_name') or '').strip()) for r in rows]


def report_recipients():
    """Return [{name, mobno, from_msg}, ...] from tbl_whatsapp_send where msg_for='SR'."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT name, mobno, from_msg
        FROM tbl_whatsapp_send
        WHERE msg_for = 'SR'
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    return rows


# -- pdf ----------------------------------------------------------------------

def _fmt(v):
    try:
        return ('%.2f' % float(v)) if v is not None else ''
    except Exception:
        return str(v or '')


def _draw_table(pdf, title, rows, grand_total):
    """Draw one titled Quality x Shift A/B/C/Total table at the current y."""
    w_q, w_n = 80.0, 25.0   # Quality + 4 numeric columns = 180mm
    row_h = 8.0

    # Title row (spans full table width).
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(w_q + 4 * w_n, row_h, title, border=1, align='C')
    pdf.ln(row_h)

    # Header line 1: Quality | Production (spans the 4 numeric columns).
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(w_q, row_h, 'Quality', border=1, align='L')
    pdf.cell(4 * w_n, row_h, 'Production', border=1, align='C')
    pdf.ln(row_h)

    # Header line 2: (blank) | Shift A | Shift B | Shift C | Total.
    pdf.cell(w_q, row_h, '', border=1)
    for label in ('Shift A', 'Shift B', 'Shift C', 'Total'):
        pdf.cell(w_n, row_h, label, border=1, align='C')
    pdf.ln(row_h)

    # Data rows.
    pdf.set_font('Helvetica', '', 10)
    for r in rows:
        pdf.cell(w_q, row_h, str(r.get('quality_name') or ''), border=1, align='L')
        pdf.cell(w_n, row_h, _fmt(r.get('shift_a')), border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('shift_b')), border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('shift_c')), border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('total')),   border=1, align='R')
        pdf.ln(row_h)

    # Grand total row.
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(w_q, row_h, 'Total', border=1, align='L')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('shift_a')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('shift_b')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('shift_c')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('total')),   border=1, align='R')
    pdf.ln(row_h)


def build_report_pdf(date_str, branch_name, spinning, winding, out_path):
    """Render the Spinning + Winding production tables to one PDF.

    spinning / winding are each (rows, grand_total) tuples.
    """
    suffix = ('  -  %s' % branch_name) if branch_name else ''
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    sp_rows, sp_gt = spinning
    _draw_table(pdf, 'Spinning Production Summary Dated %s%s' % (date_str, suffix),
                sp_rows, sp_gt)

    pdf.ln(6)  # gap between the two tables

    wd_rows, wd_gt = winding
    _draw_table(pdf, 'Winding Production report Dated %s%s' % (date_str, suffix),
                wd_rows, wd_gt)

    # Preparing date-time footer.
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(0, 6, 'Prepared on : %s' % datetime.now().strftime('%d-%m-%Y %H:%M'),
             align='R')

    pdf.output(out_path)
    return out_path


# -- send ---------------------------------------------------------------------

def _wa_clean_number(mobno):
    if not mobno:
        return None
    digits = ''.join(ch for ch in str(mobno) if ch.isdigit())
    if not digits:
        return None
    if len(digits) == 10:
        digits = os.environ.get('WHATSAPP_DEFAULT_CC', '91') + digits
    return digits


def send_daily_spg_report(report_date):
    """Build and WhatsApp the Spinning Production Summary for report_date (a date).

    One PDF per active branch, sent to every msg_for='SR' recipient.
    """
    date_str = report_date.strftime('%Y-%m-%d')
    disp_date = report_date.strftime('%d-%m-%Y')
    recipients = report_recipients()
    if not recipients:
        print('SPG report: no recipients (tbl_whatsapp_send msg_for=SR); skipping', date_str)
        return

    numbers = [n for n in (_wa_clean_number(r.get('mobno')) for r in recipients) if n]
    if not numbers:
        print('SPG report: recipients have no valid mobno; skipping', date_str)
        return

    for branch_id, branch_name in active_branches():
        try:
            sp_rows, sp_gt = fetch_spg_quality_shift(date_str, branch_id)
            wd_rows, wd_gt = fetch_winding_quality_shift(date_str, branch_id)
        except Exception as ex:
            print('SPG report: data fetch failed for branch', branch_id, ex)
            continue
        if not sp_rows and not wd_rows:
            print('SPG report: no data for branch', branch_id, 'on', date_str, '- skipping')
            continue

        fname = 'SPG_Summary_%s_%s.pdf' % (branch_id, date_str)
        out_path = os.path.join(tempfile.gettempdir(), fname)
        try:
            build_report_pdf(disp_date, branch_name,
                             (sp_rows, sp_gt), (wd_rows, wd_gt), out_path)
        except Exception as ex:
            print('SPG report: PDF build failed for branch', branch_id, ex)
            continue

        caption = 'Spinning & Winding Production Summary %s%s' % (
            disp_date, (' - ' + branch_name) if branch_name else '')
        for num in numbers:
            ok, info = send_document(num, out_path, caption=caption, filename=fname)
            print('SPG report: branch', branch_id, '-> send to', num,
                  '->', 'OK' if ok else 'FAILED', '|', info)
        try:
            os.remove(out_path)
        except Exception:
            pass


# -- scheduler ----------------------------------------------------------------

_scheduler = None

def _run_today():
    send_daily_spg_report(date.today())

def _run_yesterday():
    send_daily_spg_report(date.today() - timedelta(days=1))


def start_scheduler():
    """Start the background scheduler (15:00, 23:00 -> today; 07:00 -> yesterday).

    Idempotent within a process. Times are server local time.
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_run_today,     'cron', hour=15, minute=0, id='spg_15', replace_existing=True)
    sched.add_job(_run_today,     'cron', hour=23, minute=0, id='spg_23', replace_existing=True)
    sched.add_job(_run_yesterday, 'cron', hour=7,  minute=0, id='spg_07', replace_existing=True)
    sched.start()
    _scheduler = sched
    print('SPG report scheduler started: 15:00 & 23:00 (today), 07:00 (yesterday)')
    return sched
