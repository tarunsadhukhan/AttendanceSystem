"""Daily Summary Report (MIS01) — formatted PDF, scheduled email.

Reproduces the legacy "Daily Summary Report" (Report No [MIS01]) as a real
bordered-table PDF (same fpdf style as the SPG spinning/winding report), scoped
to one company + branch in the `sjm` DB:

    DSR_CO_ID      (default 153)  -> company name from co_mst
    DSR_BRANCH_IDS (default 106)  -> data scope (comma-separated branch ids)

There is NO upstream source for this report, so only panels with a confident data
source are populated:
  WIRED  : JUTE (Opening/Receipt/Issue/Closing, Qtl = kg/100),
           Hands Complements -> Total Hands, Units -> Electricity Units.
  BLANK  : everything else (Drawing/Spinning/Weaving/Winding/Finishing/Loose Stock,
           JBO/RBO, batch price, ...) — labels kept so fields can be wired later.

"To Day" = the report date.  "To Date" = month-to-date (1st of month .. report date).

Schedule + recipients come from tbl_whatsapp_send (msg_for = DSR_REPORT_MSG_FOR,
default 'DSR'): email_id = recipient, sch_times = HH:MM list ('P' suffix = prev day).
"""
import os
import tempfile
from datetime import date, datetime, timedelta

from fpdf import FPDF

from db import get_db
from src.send_email import send_document

DSR_CO_ID = int(os.getenv('DSR_CO_ID', '153'))
DSR_BRANCH_IDS = [int(x) for x in os.getenv('DSR_BRANCH_IDS', '106').split(',') if x.strip()]


# -- data ---------------------------------------------------------------------

def _company_name():
    """Company name for DSR_CO_ID from co_mst (defensive)."""
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT co_name FROM co_mst WHERE co_id = %s", (DSR_CO_ID,))
        row = cur.fetchone()
        cur.close(); db.close()
        return (row[0] if row and row[0] else 'Company')
    except Exception:
        return 'Company'


def _gather(report_date):
    """Collect the wired metrics for report_date (branch scope = DSR_BRANCH_IDS).

    Each query is defensive (a failure leaves that metric at 0).
    To Day = report date; To Date = month-to-date (1st of month .. report date).
    """
    d = report_date
    mtd_from = d.replace(day=1)
    vals = {k: 0.0 for k in (
        'jute_open', 'jute_rcpt_d', 'jute_rcpt_m', 'jute_iss_d', 'jute_iss_m', 'jute_close',
        'hands_d', 'hands_m', 'units_d', 'units_m')}

    bids = DSR_BRANCH_IDS
    if not bids:
        return vals
    inc = '(' + ','.join(['%s'] * len(bids)) + ')'
    bp = tuple(bids)

    db = get_db()
    cur = db.cursor()

    def scal(sql, params):
        try:
            cur.execute(sql, params)
            r = cur.fetchone()
            return float((r[0] if r else 0) or 0)
        except Exception as ex:
            print('DSR report: query failed:', ex)
            return 0.0

    # Jute (kg). Qtl conversion (/100) happens at render time.
    recv_before = scal("SELECT COALESCE(SUM(weight),0) FROM tbl_jute_received "
                       "WHERE branch_id IN %s AND recv_date < %s" % (inc, '%s'), bp + (d,))
    iss_before = scal("SELECT COALESCE(SUM(net_wt),0) FROM assorting_entry "
                      "WHERE branch_id IN %s AND entry_date < %s" % (inc, '%s'), bp + (d,))
    rcpt_d = scal("SELECT COALESCE(SUM(weight),0) FROM tbl_jute_received "
                  "WHERE branch_id IN %s AND recv_date BETWEEN %s AND %s" % (inc, '%s', '%s'), bp + (d, d))
    rcpt_m = scal("SELECT COALESCE(SUM(weight),0) FROM tbl_jute_received "
                  "WHERE branch_id IN %s AND recv_date BETWEEN %s AND %s" % (inc, '%s', '%s'), bp + (mtd_from, d))
    iss_d = scal("SELECT COALESCE(SUM(net_wt),0) FROM assorting_entry "
                 "WHERE branch_id IN %s AND entry_date BETWEEN %s AND %s" % (inc, '%s', '%s'), bp + (d, d))
    iss_m = scal("SELECT COALESCE(SUM(net_wt),0) FROM assorting_entry "
                 "WHERE branch_id IN %s AND entry_date BETWEEN %s AND %s" % (inc, '%s', '%s'), bp + (mtd_from, d))
    opening = recv_before - iss_before
    vals['jute_open'] = opening
    vals['jute_rcpt_d'] = rcpt_d
    vals['jute_rcpt_m'] = rcpt_m
    vals['jute_iss_d'] = iss_d
    vals['jute_iss_m'] = iss_m
    vals['jute_close'] = opening + rcpt_d - iss_d

    # Hands = SUM(working - idle)/8.
    hands_sql = ("SELECT COALESCE(SUM(working_hours - COALESCE(idle_hours,0)),0)/8 "
                 "FROM daily_attendance WHERE branch_id IN %s AND COALESCE(is_active,1)=1 "
                 "AND attendance_date BETWEEN %s AND %s" % (inc, '%s', '%s'))
    vals['hands_d'] = scal(hands_sql, bp + (d, d))
    vals['hands_m'] = scal(hands_sql, bp + (mtd_from, d))

    # Units = electricity units.
    elec_sql = ("SELECT COALESCE(SUM(elec_unit),0) FROM tbl_other_entries "
                "WHERE branch_id IN %s AND tran_date BETWEEN %s AND %s" % (inc, '%s', '%s'))
    vals['units_d'] = scal(elec_sql, bp + (d, d))
    vals['units_m'] = scal(elec_sql, bp + (mtd_from, d))

    cur.close(); db.close()
    return vals


# -- panel model --------------------------------------------------------------

def _n(v, dec=0):
    """Render a number; blank for 0/None (matching the register's empty cells)."""
    if not v:
        return ''
    return ('%.*f' % (dec, v)) if dec else str(int(round(v)))


def _qtl(kg):
    return _n(kg / 100.0) if kg else ''


def _blank(label, ncols):
    return [label] + [''] * ncols


def build_panels(report_date, vals):
    """Return the ordered list of report panels: {title, headers, widths, rows}.

    Pure (no DB) so it is unit-testable. rows are pre-formatted string cells.
    """
    panels = []

    # 1. JUTE  (wired)
    panels.append({
        'title': 'JUTE',
        'headers': ['Particulars', 'To Day', 'To Date'],
        'widths': [120, 55, 55],
        'rows': [
            ['Opening Stock (Qtl)', _qtl(vals['jute_open']), ''],
            ['Receipt Qty (Qtl)', _qtl(vals['jute_rcpt_d']), _qtl(vals['jute_rcpt_m'])],
            ['Issue Qty (Qtl)', _qtl(vals['jute_iss_d']), _qtl(vals['jute_iss_m'])],
            ['Delivery (Qtl)', '', ''],
            ['Adjustment (Qtl)', '', ''],
            ['Closing Stock (Qtl)', _qtl(vals['jute_close']), ''],
            ['Batch Price', '', ''],
        ],
    })

    # 2. HANDS COMPLEMENTS  (Total Hands wired)
    panels.append({
        'title': 'HANDS COMPLEMENTS',
        'headers': ['Particulars', 'To Day', 'To Date'],
        'widths': [120, 55, 55],
        'rows': [
            ['Total Hands', _n(vals['hands_d']), _n(vals['hands_m'])],
            _blank('Yarn Hands', 2), _blank('Hands/Mt Spg', 2), _blank('Hands/Mt Wvg', 2),
            _blank('Hands/Mt Yarn', 2), _blank('Hands/Mt Roll', 2),
        ],
    })

    # 3. PRODUCTION INDICES  (Units wired)
    panels.append({
        'title': 'PRODUCTION INDICES',
        'headers': ['Particulars', 'To Day', 'To Date'],
        'widths': [120, 55, 55],
        'rows': [
            ['Units', _n(vals['units_d']), _n(vals['units_m'])],
            _blank('Units/Mt', 2), _blank('Wastage (%)', 2), _blank('Wnd-Wvg Diff (%)', 2),
            _blank('Hy/Lt %', 2),
            _blank('Hessian(J) OBJ', 2), _blank('Hessian(J) Cor', 2),
            _blank('Hessian(R) Obj', 2), _blank('Hessian(R) Cor', 2),
            _blank('Sacking(J) Obj', 2), _blank('Sacking(J) Cor', 2),
            _blank('Sacking(R) Obj', 2), _blank('Sacking(R) Cor', 2),
        ],
    })

    # 4. DRAWING
    panels.append({
        'title': 'DRAWING',
        'headers': ['Quality', 'Eff% Day', 'UT% Day', 'Eff% Date', 'UT% Date',
                    'Eff% Hi', 'Ut% Hi', 'Hi Date'],
        'widths': [56, 30, 30, 30, 30, 30, 30, 42],
        'rows': [_blank(x, 7) for x in (
            '1st Drawing Fine', '1st Drawing Coarse', '2nd Drawing Fine',
            '3rd Drawing Fine', '3rd Drawing Coarse')],
    })

    # 5. SPINNING
    spin_w = [44, 24, 27, 21, 24, 27, 21, 22, 28, 22]
    panels.append({
        'title': 'SPINNING',
        'headers': ['Side', 'Frames Day', 'M.Ton Day', 'Eff% Day',
                    'Frames Date', 'M.Ton Date', 'Eff% Date', 'Eff% Hi', 'Hi Date', 'Av/Day'],
        'widths': spin_w,
        'rows': [_blank(x, 9) for x in (
            'Fine Side - J', 'Fine Side - R', 'Hy Fine - J', 'Hy Fine - R',
            'Coarse Side - J', 'Coarse Side - R', 'Total')],
    })

    # 6. WEAVING
    panels.append({
        'title': 'WEAVING',
        'headers': ['Quality', 'Looms Day', 'M.Ton Day', 'Eff% Day',
                    'Looms Date', 'M.Ton Date', 'Eff% Date', 'Eff% Hi', 'Hi Date', 'Av/Day'],
        'widths': spin_w,
        'rows': [_blank(x, 9) for x in (
            'Hessian - J', 'Hessian - R', 'Sacking - J', 'Sacking - R',
            'Hess/Sack - J', 'Hess/Sack - R', 'Total')],
    })

    # 7. WINDING (PRD/WINDER)
    panels.append({
        'title': 'WINDING (PRD/WINDER)',
        'headers': ['Particulars', 'To Day', 'To Date'],
        'widths': [120, 55, 55],
        'rows': [_blank(x, 2) for x in (
            'HS/WP/O', 'HS/WP/M', 'HS/WP/B', 'HS/WT/O', 'HS/WT/M', 'HS/WT/B',
            'SK/WP/O', 'SK/WP/M', 'SK/WP/B', 'SK/WT/O', 'SK/WT/M', 'SK/WT/B',
            'Beaming M/c', 'Beaming Cuts', 'Avgr')],
    })

    # 8. FINISHING
    panels.append({
        'title': 'FINISHING',
        'headers': ['Item', 'M/C Day', 'Bags Day', 'Bgs/Unt Day',
                    'M/C Date', 'Bags Date', 'Bgs/Unt Date'],
        'widths': [56, 30, 33, 33, 30, 33, 33],
        'rows': [_blank(x, 6) for x in (
            'Wvg Bags', 'Cutting(M/C)', 'Hand Cutting', 'Union', 'H/Sewing', 'Packed',
            'Hemming', 'Heracle', 'Press Hs', 'Press SK', 'Pr R/pk Hs', 'Pr R/pk SK', 'Pr Outside')],
    })

    # 9. LOOSE STOCK
    panels.append({
        'title': 'LOOSE STOCK',
        'headers': ['Particulars', 'Hessian', 'Sacking', 'Sale Yn', 'G/Cutt', 'P/Sheet', 'Total'],
        'widths': [60, 32, 32, 30, 30, 30, 34],
        'rows': [_blank(x, 6) for x in (
            'Opening Stock (Mt)', 'Weaving Prod (Mt) +', 'Pkd Prd(in) (Mt) -',
            'Pkd Prd(Out)(Mt) -', 'Adjustment (Mt)', 'Closing Stock (Mt)',
            'MTD Pkd Prd(In)(Mt)', 'MTD Pkd Prd(out)(Mt)')],
    })

    # 10. SHIFTS & BALES
    panels.append({
        'title': 'SHIFTS & BALES STOCK',
        'headers': ['Particulars', 'To Day', 'To Date'],
        'widths': [120, 55, 55],
        'rows': [_blank(x, 2) for x in (
            'No of Shift (Spg) - F/Side', 'No of Shift (Spg) - C/Side',
            'No of Shift (Wvg) - Hessian', 'No of Shift (Wvg) - Sacking',
            'Bales Stock (Hs)', 'Bales Stock (Sk)')],
    })

    return panels


# -- pdf (bordered tables, SPG-report style) ----------------------------------

def _draw_panel(pdf, panel, page_bottom):
    widths, headers, rows = panel['widths'], panel['headers'], panel['rows']
    total_w = sum(widths)
    rh = 6.0

    def header_block():
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(total_w, rh, panel['title'], border=1, align='C')
        pdf.ln(rh)
        pdf.set_font('Helvetica', 'B', 8)
        for w, h in zip(widths, headers):
            pdf.cell(w, rh, h, border=1, align='C')
        pdf.ln(rh)

    # Keep title+header+1 row together.
    if pdf.get_y() + 3 * rh > page_bottom:
        pdf.add_page()
    header_block()

    pdf.set_font('Helvetica', '', 8)
    for r in rows:
        if pdf.get_y() + rh > page_bottom:
            pdf.add_page()
            header_block()
            pdf.set_font('Helvetica', '', 8)
        pdf.cell(widths[0], rh, str(r[0]), border=1, align='L')
        for w, v in zip(widths[1:], r[1:]):
            pdf.cell(w, rh, str(v), border=1, align='R')
        pdf.ln(rh)
    pdf.ln(2)


def build_dsr_pdf(report_date, vals, company, out_path):
    panels = build_panels(report_date, vals)
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.set_margins(8, 8, 8)
    pdf.add_page()
    page_bottom = pdf.h - pdf.b_margin
    avail = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(avail, 7, company, align='C')
    pdf.ln(8)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(avail * 0.7, 6, 'Daily Summary Report  Dated %s (%s)' % (
        report_date.strftime('%d/%m/%Y'), report_date.strftime('%A')), align='L')
    pdf.cell(avail * 0.3, 6, 'Report No:[MIS01]', align='R')
    pdf.ln(9)

    for panel in panels:
        _draw_panel(pdf, panel, page_bottom)

    if pdf.get_y() + 16 > page_bottom:
        pdf.add_page()
    pdf.ln(2)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, '*** JBO Conversion 1 ltr = 0.88 kgs ***', ln=1)
    now = datetime.now()
    pdf.cell(0, 5, 'Report Printing Date : %s   Time %s' % (
        now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S')), ln=1)
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, '   ASST.COMM.MANAGER          ADMIN. MANAGER          '
                   'GENERAL MANAGER          PRESIDENT(W)', ln=1)

    pdf.output(out_path)
    return out_path


# -- send ---------------------------------------------------------------------

def dsr_recipients():
    code = os.getenv('DSR_REPORT_MSG_FOR', 'DSR').strip() or 'DSR'
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT email_id FROM tbl_whatsapp_send WHERE msg_for = %s", (code,))
    rows = cur.fetchall()
    cur.close(); db.close()
    emails = []
    for r in rows:
        email = (r.get('email_id') or '').strip()
        if email and email not in emails:
            emails.append(email)
    return emails


def send_daily_summary_report(report_date, recipients=None):
    """Build the Daily Summary Report (MIS01) PDF (co=DSR_CO_ID) and email it.

    recipients = explicit emails (per-recipient scheduler); None = all msg_for='DSR'.
    """
    date_str = report_date.strftime('%Y-%m-%d')
    emails = [e for e in recipients if e] if recipients is not None else dsr_recipients()
    if not emails:
        print('DSR report: no recipients; skipping', date_str)
        return
    try:
        vals = _gather(report_date)
        company = _company_name()
    except Exception as ex:
        print('DSR report: data build failed:', ex)
        return

    fname = 'daily_summary_%s.pdf' % date_str
    out_path = os.path.join(tempfile.gettempdir(), fname)
    try:
        build_dsr_pdf(report_date, vals, company, out_path)
    except Exception as ex:
        print('DSR report: PDF build failed:', ex)
        return

    caption = 'Daily Summary Report (MIS01) - %s' % report_date.strftime('%d/%m/%Y')
    body = '%s\n\nPlease find the attached report.' % caption
    for email in emails:
        ok, info = send_document(email, out_path, subject=caption, body=body, filename=fname)
        print('DSR report: email to', email, '->', 'OK' if ok else 'FAILED', '|', info)
    try:
        os.remove(out_path)
    except Exception:
        pass


# -- scheduler ----------------------------------------------------------------

_scheduler = None


def start_dsr_scheduler():
    """Start the Daily Summary Report scheduler. Times from tbl_whatsapp_send.sch_times
    (msg_for='DSR'). Idempotent per process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    from src.spg_report import start_report_scheduler
    _scheduler = start_report_scheduler('DSR report', 'DSR', send_daily_summary_report, 'dsr')
    return _scheduler


if __name__ == '__main__':
    assert _n(0) == '' and _n(None) == '' and _n(2046.0) == '2046' and _n(38.03, 2) == '38.03'
    assert _qtl(204600) == '2046' and _qtl(0) == ''
    v = {k: 0.0 for k in ('jute_open', 'jute_rcpt_d', 'jute_rcpt_m', 'jute_iss_d',
                          'jute_iss_m', 'jute_close', 'hands_d', 'hands_m', 'units_d', 'units_m')}
    v['jute_open'] = 204600; v['jute_close'] = 214400; v['hands_d'] = 890
    panels = build_panels(date(2025, 5, 31), v)
    titles = [p['title'] for p in panels]
    assert titles[0] == 'JUTE' and 'SPINNING' in titles and 'LOOSE STOCK' in titles
    jute = panels[0]
    assert jute['rows'][0] == ['Opening Stock (Qtl)', '2046', ''], jute['rows'][0]
    assert panels[1]['rows'][0] == ['Total Hands', '890', '']
    for p in panels:  # every row width matches its header
        for r in p['rows']:
            assert len(r) == len(p['headers']) == len(p['widths']), (p['title'], r)
    print('daily_summary_report self-check OK')
