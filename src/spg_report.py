"""Daily Spinning Production Summary — PDF report sent over email.

Sends a per-branch "Spinning Production Summary" PDF (quality x shift A/B/C
totals) to email recipients in tbl_whatsapp_send where msg_for in ('OE','SR')
(using the email_id column).

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
from src.send_email import send_document, fetch_hands, _hands_row_cells, _hands_add


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


def fetch_jute_details(date_str, branch_id):
    """Return (rows, grand_total) for the Jute stock ledger as on date_str.

    rows: [{quality_name, opening, received, issue, closing}, ...]
    Per jute quality (jute_quality_mst):
      Received = weight received on date_str (tbl_jute_received).
      Issue    = net_wt consumed on date_str (assorting_entry).
      Opening  = cumulative received (recv_date < date) minus cumulative
                 issued (entry_date < date).
      Closing  = opening + received - issue.
    Mirrors the Jute card logic in dashboard.py (recv vs assorting issue).
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    sql = """
        SELECT q.jute_qlty_id                            AS quality_id,
               COALESCE(q.shr_name, q.jute_quality, 'Unknown') AS quality_name,
               COALESCE(rb.w, 0)  AS opening_recv,
               COALESCE(ib.w, 0)  AS opening_issue,
               COALESCE(rd.w, 0)  AS received,
               COALESCE(id_.w, 0) AS issue
        FROM jute_quality_mst q
        LEFT JOIN (SELECT quality_id, SUM(weight) w FROM tbl_jute_received
                   WHERE recv_date < %s AND branch_id = %s GROUP BY quality_id) rb
               ON rb.quality_id = q.jute_qlty_id
        LEFT JOIN (SELECT quality_id, SUM(net_wt) w FROM assorting_entry
                   WHERE entry_date < %s AND branch_id = %s GROUP BY quality_id) ib
               ON ib.quality_id = q.jute_qlty_id
        LEFT JOIN (SELECT quality_id, SUM(weight) w FROM tbl_jute_received
                   WHERE recv_date = %s AND branch_id = %s GROUP BY quality_id) rd
               ON rd.quality_id = q.jute_qlty_id
        LEFT JOIN (SELECT quality_id, SUM(net_wt) w FROM assorting_entry
                   WHERE entry_date = %s AND branch_id = %s GROUP BY quality_id) id_
               ON id_.quality_id = q.jute_qlty_id
        WHERE q.branch_id = %s
        ORDER BY quality_name
    """
    params = (date_str, branch_id, date_str, branch_id,
              date_str, branch_id, date_str, branch_id, branch_id)
    cur.execute(sql, params)
    raw = cur.fetchall()
    cur.close(); db.close()

    rows = []
    for r in raw:
        opening  = float(r['opening_recv'] or 0) - float(r['opening_issue'] or 0)
        received = float(r['received'] or 0)
        issue    = float(r['issue'] or 0)
        closing  = opening + received - issue
        # Skip qualities with no opening balance and no movement on the day.
        if opening == 0 and received == 0 and issue == 0:
            continue
        rows.append({
            'quality_name': r['quality_name'],
            'opening':  opening,
            'received': received,
            'issue':    issue,
            'closing':  closing,
        })
    return rows, _jute_grand_total(rows)


def fetch_finishing_shift(date_str):
    """Return (rows, grand_total=None) for the Other Entries (finishing) summary.

    Pivots tbl_daily_finishing: one row per item (Looms, Cuts, ...) with
    Shift A/B/C and Total columns. The table has no branch column, so the
    figures are company-wide. grand_total is None (items have mixed units,
    summing them is meaningless).
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT COALESCE(s.spell_name, '') AS spell_name,
               f.looms, f.cuts, f.hemming, f.heracle, f.cutting,
               f.branding, f.hand_sewer, f.bales, f.issue_bales
        FROM tbl_daily_finishing f
        LEFT JOIN spell_mst s ON f.spell_id = s.spell_id
        WHERE f.tran_date = %s
    """, (date_str,))
    raw = cur.fetchall()
    cur.close(); db.close()

    items = [('looms', 'Looms'), ('cuts', 'Cuts'), ('hemming', 'Hemming'),
             ('heracle', 'Heracle'), ('cutting', 'Cutting'),
             ('branding', 'Branding'), ('hand_sewer', 'Hand Sewer'),
             ('bales', 'Bales'), ('issue_bales', 'Issue Bales')]
    rows = []
    for col, label in items:
        if all(r[col] is None for r in raw):
            continue  # item never entered on this date
        def _shift(letter):
            return sum(float(r[col] or 0) for r in raw
                       if letter in (r['spell_name'] or '').upper())
        rows.append({
            'quality_name': label,
            'shift_a': _shift('A'),
            'shift_b': _shift('B'),
            'shift_c': _shift('C'),
            'total':   sum(float(r[col] or 0) for r in raw),
        })
    return rows, None


def fetch_drawing_summary(date_str, branch_id):
    """Return (rows, None) for the Drawing report: per-machine units + efficiency.

    rows: [{mc_name, units, eff}, ...] aggregated over all spells of the day.
    Efficiency uses the same formula as POST /drawing/entry:
        eff = units / (const_meter / 8 * running_hours) * 100
    with units and running_hours summed across the day per machine.
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT m.short_name              AS mc_name,
               SUM(d.difference)         AS units,
               SUM(d.running_hours)      AS running_hours,
               MAX(d.const_meter)        AS const_meter
        FROM tbl_daily_drawing d
        JOIN tbl_drawing_mst m ON m.mc_id = d.mc_id
        WHERE d.tran_date = %s AND d.branch_id = %s
        GROUP BY d.mc_id, m.short_name
        ORDER BY m.short_name
    """, (date_str, branch_id))
    raw = cur.fetchall()
    cur.close(); db.close()

    rows = []
    for r in raw:
        units = float(r['units'] or 0)
        rh    = float(r['running_hours'] or 0)
        cm    = float(r['const_meter'] or 0)
        eff   = round(units / (cm / 8 * rh) * 100, 2) if rh > 0 and cm > 0 else 0.0
        rows.append({'mc_name': r['mc_name'] or '', 'units': units, 'eff': eff})
    return rows, None


def _grand_total(rows):
    return {
        'shift_a': sum(float(r['shift_a'] or 0) for r in rows),
        'shift_b': sum(float(r['shift_b'] or 0) for r in rows),
        'shift_c': sum(float(r['shift_c'] or 0) for r in rows),
        'total':   sum(float(r['total']   or 0) for r in rows),
    }


def _jute_grand_total(rows):
    return {
        'opening':  sum(float(r['opening']  or 0) for r in rows),
        'received': sum(float(r['received'] or 0) for r in rows),
        'issue':    sum(float(r['issue']    or 0) for r in rows),
        'closing':  sum(float(r['closing']  or 0) for r in rows),
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
    branches = [(r['branch_id'], (r.get('branch_name') or '').strip()) for r in rows]

    # Optional .env filter: SPG_REPORT_BRANCHES=103 (comma-separated branch ids).
    # Blank/missing = all active branches.
    wanted = os.getenv('SPG_REPORT_BRANCHES', '').strip()
    if wanted:
        try:
            ids = {int(b) for b in wanted.split(',') if b.strip()}
        except ValueError:
            print('SPG report: invalid SPG_REPORT_BRANCHES=%r; using all branches' % wanted)
            return branches
        branches = [b for b in branches if b[0] in ids]
        if not branches:
            print('SPG report: SPG_REPORT_BRANCHES=%r matched no active branch' % wanted)
    return branches


def report_recipients():
    """Return [{name, mobno, from_msg, email_id}, ...] from tbl_whatsapp_send where msg_for in ('OE','SR')."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT name, mobno, from_msg, email_id
        FROM tbl_whatsapp_send
        WHERE msg_for IN ('OE', 'SR')
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


def _draw_table(pdf, title, rows, grand_total, first_col='Quality'):
    """Draw one titled Quality x Shift A/B/C/Total table at the current y.

    grand_total=None omits the bottom Total row (used when row units differ).
    """
    w_q, w_n = 80.0, 25.0   # Quality + 4 numeric columns = 180mm
    row_h = 8.0

    # Title row (spans full table width).
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(w_q + 4 * w_n, row_h, title, border=1, align='C')
    pdf.ln(row_h)

    # Header line 1: Quality | Production (spans the 4 numeric columns).
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(w_q, row_h, first_col, border=1, align='L')
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
    if grand_total is None:
        return
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(w_q, row_h, 'Total', border=1, align='L')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('shift_a')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('shift_b')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('shift_c')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('total')),   border=1, align='R')
    pdf.ln(row_h)


def _draw_jute_table(pdf, title, rows, grand_total):
    """Draw the Quality | Opening | Received | Issue | Closing jute ledger table."""
    w_q, w_n = 80.0, 25.0   # Quality + 4 numeric columns = 180mm
    row_h = 8.0

    # Title row (spans full table width).
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(w_q + 4 * w_n, row_h, title, border=1, align='C')
    pdf.ln(row_h)

    # Header row.
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(w_q, row_h, 'Quality', border=1, align='L')
    for label in ('Opening', 'Received', 'Issue', 'Closing'):
        pdf.cell(w_n, row_h, label, border=1, align='C')
    pdf.ln(row_h)

    # Data rows.
    pdf.set_font('Helvetica', '', 10)
    for r in rows:
        pdf.cell(w_q, row_h, str(r.get('quality_name') or ''), border=1, align='L')
        pdf.cell(w_n, row_h, _fmt(r.get('opening')),  border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('received')), border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('issue')),    border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('closing')),  border=1, align='R')
        pdf.ln(row_h)

    # Total row.
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(w_q, row_h, 'Total', border=1, align='L')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('opening')),  border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('received')), border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('issue')),    border=1, align='R')
    pdf.cell(w_n, row_h, _fmt(grand_total.get('closing')),  border=1, align='R')
    pdf.ln(row_h)


def _draw_drawing_table(pdf, title, rows):
    """Draw the Drawing report: MC Name | Units | Efficiency %."""
    w_mc, w_n = 100.0, 40.0   # 100 + 2*40 = 180mm
    row_h = 8.0

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(w_mc + 2 * w_n, row_h, title, border=1, align='C')
    pdf.ln(row_h)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(w_mc, row_h, 'Machine', border=1, align='L')
    pdf.cell(w_n, row_h, 'Units', border=1, align='C')
    pdf.cell(w_n, row_h, 'Efficiency %', border=1, align='C')
    pdf.ln(row_h)

    pdf.set_font('Helvetica', '', 10)
    tot_units = 0.0
    for r in rows:
        tot_units += float(r.get('units') or 0)
        pdf.cell(w_mc, row_h, str(r.get('mc_name') or ''), border=1, align='L')
        pdf.cell(w_n, row_h, _fmt(r.get('units')), border=1, align='R')
        pdf.cell(w_n, row_h, _fmt(r.get('eff')),   border=1, align='R')
        pdf.ln(row_h)

    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(w_mc, row_h, 'Total', border=1, align='L')
    pdf.cell(w_n, row_h, _fmt(tot_units), border=1, align='R')
    pdf.cell(w_n, row_h, '', border=1)
    pdf.ln(row_h)


def _draw_hands_table(pdf, title, rows):
    """Draw the man-machine Hands report (Particulars x shift M/H + Hands), portrait.

    rows = fetch_hands() output (dept_desc/dept_code/desig + thands_a/b/c, hands_a/b/c),
    grouped by department with per-section subtotals and a grand total. Reuses the
    cell/accumulator helpers from send_email so figures match the standalone PDF.
    """
    w_p, w_n = 52.0, 16.0   # 52 + 8*16 = 180mm (portrait usable)
    row_h = 6.0

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(w_p + 8 * w_n, row_h, title, border=1, align='C')
    pdf.ln(row_h)

    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(w_p, row_h, 'Particulars', border=1, align='L')
    for label in ('Shift A', 'Shift B', 'Shift C', 'Total'):
        pdf.cell(2 * w_n, row_h, label, border=1, align='C')
    pdf.ln(row_h)
    pdf.cell(w_p, row_h, '', border=1)
    for _ in range(4):
        pdf.cell(w_n, row_h, 'M/H', border=1, align='C')
        pdf.cell(w_n, row_h, 'Hands', border=1, align='C')
    pdf.ln(row_h)

    def numeric_row(label, cells, bold=False):
        pdf.set_font('Helvetica', 'B' if bold else '', 7)
        pdf.cell(w_p, row_h, label, border=1, align='L')
        for c in cells:
            pdf.cell(w_n, row_h, c, border=1, align='R')
        pdf.ln(row_h)

    grand, sub = {}, {}
    cur_dept, sub_label = None, ''

    def flush_sub():
        if cur_dept is not None:
            numeric_row('  Sub Total - %s' % sub_label, _hands_row_cells(sub), bold=True)

    for r in rows:
        dept = (r.get('dept_code'), r.get('dept_desc'))
        if dept != cur_dept:
            flush_sub()
            cur_dept = dept
            sub = {}
            sub_label = (r.get('dept_desc') or '').strip()
            pdf.set_font('Helvetica', 'B', 8)
            pdf.cell(w_p + 8 * w_n, row_h, sub_label or 'Others', border=1, align='L')
            pdf.ln(row_h)
        numeric_row('   %s' % (r.get('desig') or ''), _hands_row_cells(r))
        _hands_add(sub, r); _hands_add(grand, r)

    flush_sub()
    numeric_row('Total as per above', _hands_row_cells(grand), bold=True)


def build_report_pdf(date_str, branch_name, jute, spinning, winding, out_path,
                     finishing=None, drawing=None, hands=None):
    """Render Jute + Spinning + Winding + Hands + Drawing (+ Other Entries) tables.

    jute / spinning / winding / finishing are (rows, grand_total) tuples; drawing is
    (rows, None); hands is the fetch_hands() row list. hands, drawing and finishing
    are optional and drawn only when they have rows.
    """
    suffix = ('  -  %s' % branch_name) if branch_name else ''
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    jt_rows, jt_gt = jute
    _draw_jute_table(pdf, 'Jute Details As on %s%s' % (date_str, suffix),
                     jt_rows, jt_gt)

    pdf.ln(6)  # gap before the spinning table

    sp_rows, sp_gt = spinning
    _draw_table(pdf, 'Spinning Production Summary Dated %s%s' % (date_str, suffix),
                sp_rows, sp_gt)

    pdf.ln(6)  # gap between the two tables

    wd_rows, wd_gt = winding
    _draw_table(pdf, 'Winding Production report Dated %s%s' % (date_str, suffix),
                wd_rows, wd_gt)

    if hands:
        pdf.ln(6)
        _draw_hands_table(pdf, 'Hands Report Dated %s%s' % (date_str, suffix), hands)

    if drawing and drawing[0]:
        pdf.ln(6)
        dr_rows, _ = drawing
        _draw_drawing_table(pdf, 'Drawing Report Dated %s%s' % (date_str, suffix),
                            dr_rows)

    if finishing and finishing[0]:
        pdf.ln(6)
        fn_rows, fn_gt = finishing
        _draw_table(pdf, 'Other Entries Dated %s' % date_str,
                    fn_rows, fn_gt, first_col='Particulars')

    # Preparing date-time footer.
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(0, 6, 'Prepared on : %s' % datetime.now().strftime('%d-%m-%Y %H:%M'),
             align='R')

    pdf.output(out_path)
    return out_path


# -- send ---------------------------------------------------------------------

def send_daily_spg_report(report_date, recipients=None):
    """Build and email the Spinning Production Summary for report_date (a date).

    One PDF per active branch. recipients = explicit list of emails (used by the
    per-recipient scheduler); None = every msg_for in ('OE','SR') recipient (manual run).
    """
    date_str = report_date.strftime('%Y-%m-%d')
    disp_date = report_date.strftime('%d-%m-%Y')

    if recipients is not None:
        emails = [e for e in recipients if e]
    else:
        emails = []
        for r in report_recipients():
            email = (r.get('email_id') or '').strip()
            if email and email not in emails:
                emails.append(email)
    if not emails:
        print('SPG report: no recipients; skipping', date_str)
        return

    # Other Entries (tbl_daily_finishing) has no branch column: fetch once,
    # company-wide, and include the same table in every branch PDF.
    try:
        fn_rows, fn_gt = fetch_finishing_shift(date_str)
    except Exception as ex:
        print('SPG report: other-entries fetch failed:', ex)
        fn_rows, fn_gt = [], None

    for branch_id, branch_name in active_branches():
        try:
            jt_rows, jt_gt = fetch_jute_details(date_str, branch_id)
            sp_rows, sp_gt = fetch_spg_quality_shift(date_str, branch_id)
            wd_rows, wd_gt = fetch_winding_quality_shift(date_str, branch_id)
            dr_rows, _     = fetch_drawing_summary(date_str, branch_id)
            hd_rows        = fetch_hands(date_str, branch_id)
        except Exception as ex:
            print('SPG report: data fetch failed for branch', branch_id, ex)
            continue
        if not jt_rows and not sp_rows and not wd_rows and not fn_rows and not dr_rows and not hd_rows:
            print('SPG report: no data for branch', branch_id, 'on', date_str, '- skipping')
            continue

        fname = 'SPG_Summary_%s_%s.pdf' % (branch_id, date_str)
        out_path = os.path.join(tempfile.gettempdir(), fname)
        try:
            build_report_pdf(disp_date, branch_name,
                             (jt_rows, jt_gt), (sp_rows, sp_gt), (wd_rows, wd_gt),
                             out_path, finishing=(fn_rows, fn_gt),
                             drawing=(dr_rows, None), hands=hd_rows)
        except Exception as ex:
            print('SPG report: PDF build failed for branch', branch_id, ex)
            continue

        caption = 'Spinning & Winding Production Summary %s%s' % (
            disp_date, (' - ' + branch_name) if branch_name else '')
        body = '%s\n\nPlease find the attached report.' % caption
        for email in emails:
            ok, info = send_document(email, out_path, subject=caption,
                                     body=body, filename=fname)
            print('SPG report: branch', branch_id, '-> email to', email,
                  '->', 'OK' if ok else 'FAILED', '|', info)
        try:
            os.remove(out_path)
        except Exception:
            pass


# -- scheduler ----------------------------------------------------------------

_scheduler = None


def _parse_hhmm(part):
    """Parse a single 'HH:MM' into (hour, minute), or None if invalid."""
    part = part.strip()
    if not part:
        return None
    try:
        hh, _, mm = part.partition(':')
        hour, minute = int(hh), int(mm or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
        print('report schedule: ignoring out-of-range time %r' % part)
    except ValueError:
        print('report schedule: ignoring invalid time %r' % part)
    return None


def _split_times(s):
    """Parse one sch_times string into (today_times, prevday_times) lists of
    (hour, minute). A time with a trailing 'P' (e.g. '07:00P') is a previous-day run."""
    today, prev = [], []
    for part in str(s or '').split(','):
        part = part.strip()
        if not part:
            continue
        is_prev = part[-1:].upper() == 'P'
        hm = _parse_hhmm(part[:-1] if is_prev else part)
        if hm is None:
            continue
        (prev if is_prev else today).append(hm)
    return today, prev


def scheduled_times(msg_for):
    """Union of every matching row's sch_times for a msg_for code (or list).

    Returns (today_times, prevday_times), each a sorted, de-duped list of
    (hour, minute). Mainly a diagnostic / overview helper; live per-recipient
    scheduling uses due_recipients().
    """
    codes = [c for c in (msg_for if isinstance(msg_for, (list, tuple)) else [msg_for]) if c]
    if not codes:
        return [], []
    try:
        db = get_db()
        cur = db.cursor()
        ph = ','.join(['%s'] * len(codes))
        cur.execute("SELECT sch_times FROM tbl_whatsapp_send "
                    "WHERE msg_for IN (%s) AND sch_times IS NOT NULL AND sch_times <> ''" % ph,
                    tuple(codes))
        raw = [r[0] for r in cur.fetchall()]
        cur.close(); db.close()
    except Exception as ex:
        print('report schedule: sch_times lookup failed:', ex)
        return [], []
    today, prev = [], []
    for s in raw:
        t, p = _split_times(s)
        today += [x for x in t if x not in today]
        prev += [x for x in p if x not in prev]
    today.sort(); prev.sort()
    return today, prev


def due_recipients(msg_for):
    """Recipients due at the CURRENT minute, per row (per-recipient scheduling).

    Each tbl_whatsapp_send row carries its own sch_times, so the same report
    (msg_for) can reach different people at different times. Returns
    (today_emails, prevday_emails) for the current HH:MM. email_id may hold several
    comma-separated addresses; msg_for is a code or list of codes.
    """
    codes = [c for c in (msg_for if isinstance(msg_for, (list, tuple)) else [msg_for]) if c]
    if not codes:
        return [], []
    try:
        db = get_db()
        cur = db.cursor()
        ph = ','.join(['%s'] * len(codes))
        cur.execute("SELECT email_id, sch_times FROM tbl_whatsapp_send "
                    "WHERE msg_for IN (%s) AND email_id IS NOT NULL AND email_id <> '' "
                    "AND sch_times IS NOT NULL AND sch_times <> ''" % ph, tuple(codes))
        rows = cur.fetchall()
        cur.close(); db.close()
    except Exception as ex:
        print('report schedule: due_recipients lookup failed:', ex)
        return [], []
    now = datetime.now()
    hm = (now.hour, now.minute)
    today, prev = [], []
    for email_id, sch in rows:
        t_times, p_times = _split_times(sch)
        addrs = [a.strip() for a in str(email_id).split(',') if a.strip()]
        if hm in t_times:
            today += [a for a in addrs if a not in today]
        if hm in p_times:
            prev += [a for a in addrs if a not in prev]
    return today, prev


def _report_tick(label, msg_for, send_fn):
    """Per-minute tick: send the report to whichever recipients are due this minute.

    Reads tbl_whatsapp_send live (per-row sch_times), so schedule/recipient edits
    apply within a minute, no restart. send_fn(report_date, emails) does the send;
    'P'-suffixed times send the previous day's report.
    """
    today_emails, prev_emails = due_recipients(msg_for)
    if today_emails:
        print('%s: sending (current day) to %d recipient(s)' % (label, len(today_emails)))
        try:
            send_fn(date.today(), today_emails)
        except Exception as ex:
            print('%s: run failed:' % label, ex)
    if prev_emails:
        print('%s: sending (previous day) to %d recipient(s)' % (label, len(prev_emails)))
        try:
            send_fn(date.today() - timedelta(days=1), prev_emails)
        except Exception as ex:
            print('%s: run failed:' % label, ex)


def start_report_scheduler(label, msg_for, send_fn, id_prefix):
    """Start a per-minute, table-driven scheduler for one daily report.

    A single cron job ticks every minute and re-reads tbl_whatsapp_send (msg_for):
    each recipient row fires at its own sch_times, so the same report can reach
    different recipients at different times. send_fn(report_date, emails) sends to the
    due recipients. Edits apply within a minute, no restart. Caller owns idempotency.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(lambda: _report_tick(label, msg_for, send_fn),
                  'cron', minute='*', id='%s_tick' % id_prefix,
                  replace_existing=True, max_instances=1, misfire_grace_time=55)
    sched.start()
    print('%s scheduler started (per-recipient, table-driven, msg_for=%s)' % (label, msg_for))
    return sched


def start_scheduler():
    """Start the SPG report scheduler (per-recipient sch_times, msg_for in OE/SR).
    Idempotent within a process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = start_report_scheduler('SPG report', ('OE', 'SR'), send_daily_spg_report, 'spg')
    return _scheduler


if __name__ == "__main__":
    # Manual one-shot run (does NOT start the scheduler):
    #   python -m src.spg_report [YYYY-MM-DD] [email ...]
    # No date -> today. No emails -> every msg_for OE/SR recipient.
    import sys
    argv = sys.argv[1:]
    rd = datetime.strptime(argv[0], '%Y-%m-%d').date() if argv else date.today()
    send_daily_spg_report(rd, argv[1:] or None)
