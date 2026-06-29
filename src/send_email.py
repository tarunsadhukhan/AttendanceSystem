"""Email sender (SMTP, stdlib only).

Sends a single email with an optional file attachment. No external packages
required (uses smtplib + email.message). Reads SMTP credentials from the
project-root .env file (or environment variables).

Configure in .env (one directory above src/):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@gmail.com
    SMTP_PASSWORD=<gmail app password, spaces removed>
    SMTP_FROM=                 # optional; defaults to SMTP_USER

Usage:
    python -m src.send_email you@example.com "Subject" "Body"
    python -m src.send_email you@example.com "Subject" "Body" /path/to/file.pdf
"""
import os
import sys
import smtplib
import mimetypes
from datetime import datetime
from email.message import EmailMessage


def _load_dotenv(filename=".env"):
    """Load KEY=VALUE lines from the project-root .env into os.environ (no deps).

    send_email.py lives in src/, so the .env is one directory up.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

# -- CONFIG (from .env / environment, with fallbacks) -------------------------
DEFAULT_HOST = "smtp.gmail.com"
DEFAULT_PORT = 587
# -----------------------------------------------------------------------------


def send_document(to_email, file_path, subject, body, filename=None):
    """Email a file as an attachment. Returns (ok, info).

    Re-reads SMTP config from the environment on each call, so a value updated
    in .env / the environment takes effect without re-importing the module.
    Never raises: any failure is returned as (False, reason).
    """
    host = os.getenv("SMTP_HOST", DEFAULT_HOST)
    try:
        port = int(os.getenv("SMTP_PORT", str(DEFAULT_PORT)))
    except ValueError:
        port = DEFAULT_PORT
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", "").strip() or user

    if not user or not password:
        return False, "SMTP not configured (set SMTP_USER and SMTP_PASSWORD in .env)."
    if not to_email:
        return False, "No recipient email address."

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject or ""
    msg.set_content(body or "")

    # Attach the file (default to application/pdf when type is unknown).
    if file_path:
        try:
            with open(file_path, "rb") as fh:
                content = fh.read()
        except Exception as e:
            return False, "Cannot read file: %s" % e
        ctype, _ = mimetypes.guess_type(file_path)
        maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "pdf"))
        msg.add_attachment(content, maintype=maintype, subtype=subtype,
                           filename=filename or os.path.basename(file_path))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True, "OK"
    except Exception as e:
        return False, str(e)


# =============================================================================
# Daily Hands Report (man vs machine) — PDF report emailed per branch.
#
# Built from the vw_man_machine view: Particulars (department -> designation)
# x shift A/B/C, each shift showing M/H (the standard = thands) and Hands
# (actual = hands), with per-section subtotals and a grand total. Modelled on
# the SARADA JUTE MILLS paper "HANDS REPORT" register.
#
# NOTE: vw_man_machine only carries 3 shifts (A/B/C); the paper register's
# Shift B1/B2 and Old Shed/New Shed splits are not in the view, so not shown.
#
# Schedule (server local time, env-configurable):
#   HANDS_REPORT_TIMES         -> CURRENT date  (default 23:00)
#   HANDS_REPORT_TIMES_PREVDAY -> PREVIOUS date (default 08:00)
# Recipients: tbl_whatsapp_send rows with msg_for = HANDS_REPORT_MSG_FOR
# (default 'HR'), using the email_id column.
#
# Heavy deps (fpdf, db, apscheduler, spg_report) are imported lazily inside the
# functions so the basic mailer above stays stdlib-only.
# =============================================================================


def fetch_hands(date_str, branch_id):
    """Return ordered rows from vw_man_machine for date_str + branch_id.

    rows: [{dept_code, dept_desc, desig, hands_a/b/c, thands_a/b/c}, ...]
    Same source as GET /otherentries/hands-report, ordered by section then desig.
    """
    from db import get_db
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT dept_desc, dept_code, desig,
               hands_a, hands_b, hands_c,
               thands_a, thands_b, thands_c
        FROM vw_man_machine
        WHERE attendance_date = %s AND branch_id = %s
        ORDER BY dept_code, dept_desc, desig
    """, (date_str, branch_id))
    rows = cur.fetchall()
    cur.close(); db.close()
    return rows


def _report_emails(code):
    """Distinct, non-blank email_ids from tbl_whatsapp_send for a msg_for code."""
    from db import get_db
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


def hands_recipients():
    """Hands report recipients (msg_for = HANDS_REPORT_MSG_FOR, default 'HR')."""
    return _report_emails(os.getenv('HANDS_REPORT_MSG_FOR', 'HR').strip() or 'HR')


def _hands_fmt(v):
    """Whole number when integral, 2dp otherwise; blank for 0/None (like the register)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ''
    if f == 0:
        return ''
    return str(int(f)) if f == int(f) else ('%.2f' % f)


# (thands=M/H, hands=Hands) column pairs per shift, in display order.
_HANDS_SHIFTS = (('thands_a', 'hands_a'), ('thands_b', 'hands_b'), ('thands_c', 'hands_c'))


def _hands_row_cells(r):
    """8 numeric strings for one data/total row: M/H, Hands per A/B/C then Total."""
    out = []
    tot_mh = tot_h = 0.0
    for mh_key, h_key in _HANDS_SHIFTS:
        mh = float(r.get(mh_key) or 0)
        h  = float(r.get(h_key) or 0)
        tot_mh += mh; tot_h += h
        out.append(_hands_fmt(mh)); out.append(_hands_fmt(h))
    out.append(_hands_fmt(tot_mh)); out.append(_hands_fmt(tot_h))
    return out


def _hands_add(acc, r):
    """Accumulate a row's 6 shift values into acc dict (for subtotals/grand total)."""
    for mh_key, h_key in _HANDS_SHIFTS:
        acc[mh_key] = acc.get(mh_key, 0.0) + float(r.get(mh_key) or 0)
        acc[h_key]  = acc.get(h_key, 0.0)  + float(r.get(h_key) or 0)


_HANDS_W_P, _HANDS_W_N, _HANDS_ROW_H = 75.0, 24.0, 6.0   # 75 + 8*24 = 267mm (A4 landscape)


def _hands_draw_header(pdf):
    """Two-line column header: Particulars | Shift A/B/C/Total x (M/H, Hands)."""
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(_HANDS_W_P, _HANDS_ROW_H, 'Particulars', border=1, align='L')
    for label in ('Shift A', 'Shift B', 'Shift C', 'Total'):
        pdf.cell(2 * _HANDS_W_N, _HANDS_ROW_H, label, border=1, align='C')
    pdf.ln(_HANDS_ROW_H)
    pdf.cell(_HANDS_W_P, _HANDS_ROW_H, '', border=1)
    for _ in range(4):
        pdf.cell(_HANDS_W_N, _HANDS_ROW_H, 'M/H', border=1, align='C')
        pdf.cell(_HANDS_W_N, _HANDS_ROW_H, 'Hands', border=1, align='C')
    pdf.ln(_HANDS_ROW_H)


def _hands_draw_numeric_row(pdf, label, cells, bold=False, fill=False):
    pdf.set_font('Helvetica', 'B' if bold else '', 8)
    pdf.cell(_HANDS_W_P, _HANDS_ROW_H, label, border=1, align='L', fill=fill)
    for c in cells:
        pdf.cell(_HANDS_W_N, _HANDS_ROW_H, c, border=1, align='R', fill=fill)
    pdf.ln(_HANDS_ROW_H)


def build_hands_pdf(disp_date, branch_name, rows, out_path):
    """Render the Hands Report PDF for one branch to out_path."""
    from fpdf import FPDF
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.set_margins(15, 12, 15)
    pdf.add_page()
    page_bottom = pdf.h - pdf.b_margin

    suffix = ('  -  %s' % branch_name) if branch_name else ''
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(_HANDS_W_P + 8 * _HANDS_W_N, 8,
             'HANDS REPORT   Dated %s%s' % (disp_date, suffix), border=1, align='C')
    pdf.ln(8)
    _hands_draw_header(pdf)

    grand = {}
    cur_dept = None
    sub = {}
    sub_label = ''

    def flush_subtotal():
        if cur_dept is not None:
            _hands_draw_numeric_row(pdf, '  Sub Total - %s' % sub_label,
                                    _hands_row_cells(sub), bold=True)

    for r in rows:
        dept = (r.get('dept_code'), r.get('dept_desc'))
        if dept != cur_dept:
            flush_subtotal()
            cur_dept = dept
            sub = {}
            sub_label = (r.get('dept_desc') or '').strip()
            if pdf.get_y() + 3 * _HANDS_ROW_H > page_bottom:
                pdf.add_page(); _hands_draw_header(pdf)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(_HANDS_W_P + 8 * _HANDS_W_N, _HANDS_ROW_H, sub_label or 'Others',
                     border=1, align='L', fill=True)
            pdf.ln(_HANDS_ROW_H)
        if pdf.get_y() + _HANDS_ROW_H > page_bottom:
            pdf.add_page(); _hands_draw_header(pdf)
        _hands_draw_numeric_row(pdf, '   %s' % (r.get('desig') or ''), _hands_row_cells(r))
        _hands_add(sub, r)
        _hands_add(grand, r)

    flush_subtotal()

    if pdf.get_y() + _HANDS_ROW_H > page_bottom:
        pdf.add_page(); _hands_draw_header(pdf)
    _hands_draw_numeric_row(pdf, 'Total as per above', _hands_row_cells(grand),
                            bold=True, fill=True)

    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, 'Prepared on : %s' % datetime.now().strftime('%d-%m-%Y %H:%M'),
             align='R')

    pdf.output(out_path)
    return out_path


def send_daily_hands_report(report_date, recipients=None):
    """Build and email the Hands Report for report_date. One PDF per branch.

    recipients = explicit emails (per-recipient scheduler); None = all msg_for='HR'.
    """
    import tempfile
    from src.spg_report import active_branches  # active-branch list (lazy: avoids import cycle)

    date_str = report_date.strftime('%Y-%m-%d')
    disp_date = report_date.strftime('%d-%m-%Y')

    emails = [e for e in recipients if e] if recipients is not None else hands_recipients()
    if not emails:
        print('Hands report: no recipients; skipping', date_str)
        return

    for branch_id, branch_name in active_branches():
        try:
            rows = fetch_hands(date_str, branch_id)
        except Exception as ex:
            print('Hands report: data fetch failed for branch', branch_id, ex)
            continue
        if not rows:
            print('Hands report: no data for branch', branch_id, 'on', date_str, '- skipping')
            continue

        fname = 'Hands_Report_%s_%s.pdf' % (branch_id, date_str)
        out_path = os.path.join(tempfile.gettempdir(), fname)
        try:
            build_hands_pdf(disp_date, branch_name, rows, out_path)
        except Exception as ex:
            print('Hands report: PDF build failed for branch', branch_id, ex)
            continue

        caption = 'Hands Report %s%s' % (disp_date, (' - ' + branch_name) if branch_name else '')
        body = '%s\n\nPlease find the attached report.' % caption
        for email in emails:
            ok, info = send_document(email, out_path, subject=caption,
                                     body=body, filename=fname)
            print('Hands report: branch', branch_id, '-> email to', email,
                  '->', 'OK' if ok else 'FAILED', '|', info)
        try:
            os.remove(out_path)
        except Exception:
            pass


_hands_scheduler = None


def start_hands_scheduler():
    """Start the Hands Report scheduler (per-recipient sch_times, msg_for='HR')."""
    global _hands_scheduler
    if _hands_scheduler is not None:
        return _hands_scheduler
    from src.spg_report import start_report_scheduler
    _hands_scheduler = start_report_scheduler('Hands report', 'HR', send_daily_hands_report, 'hands')
    return _hands_scheduler


# =============================================================================
# Daily Drawing Efficiency Report — PDF report emailed per branch.
#
# Per drawing machine x shift A/B/C (plus Overall): Units (meters drawn) and
# Efficiency %, from tbl_daily_drawing + tbl_drawing_mst. Mirrors the shift
# matrix backing /dashboardportal/productionReports/drawingReports.
#
#   eff = units / (const_meter / 8 * running_hours) * 100
# the same formula as POST /drawing/entry and spg_report.fetch_drawing_summary.
#
# Schedule (server local time, env-configurable):
#   DRAWING_REPORT_TIMES         -> CURRENT date  (default 23:00)
#   DRAWING_REPORT_TIMES_PREVDAY -> PREVIOUS date (default 08:00)
# Recipients: tbl_whatsapp_send msg_for = DRAWING_REPORT_MSG_FOR (default 'DR').
# =============================================================================


def drawing_recipients():
    """Drawing report recipients (msg_for = DRAWING_REPORT_MSG_FOR, default 'DR')."""
    return _report_emails(os.getenv('DRAWING_REPORT_MSG_FOR', 'DR').strip() or 'DR')


def _drawing_eff(units, rh, const):
    """Efficiency % = units / (const/8 * running_hours) * 100; 0 when undefined."""
    return round(units / (const / 8 * rh) * 100, 2) if rh > 0 and const > 0 else 0.0


def _drawing_shift_letter(spell_name):
    """Map a spell name to shift A/B/C (first letter found), else '' (Overall only)."""
    s = (spell_name or '').upper()
    for letter in ('A', 'B', 'C'):
        if letter in s:
            return letter
    return ''


def fetch_drawing_efficiency(date_str, branch_id):
    """Return per-machine pivoted drawing rows for date_str + branch_id.

    rows: [{mc_name, shed_type, drg_type,
            a_unit, a_eff, b_unit, b_eff, c_unit, c_eff, o_unit, o_eff}, ...]
    ordered by shed_type, drg_type, machine. Overall sums every spell (incl.
    spells that don't map to A/B/C) so totals are never undercounted.
    """
    from db import get_db
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT m.short_name              AS mc_name,
               m.shed_type               AS shed_type,
               m.drg_type                AS drg_type,
               COALESCE(sp.spell_name,'') AS spell_name,
               SUM(d.difference)         AS units,
               SUM(d.running_hours)      AS running_hours,
               MAX(d.const_meter)        AS const_meter
        FROM tbl_daily_drawing d
        JOIN tbl_drawing_mst m ON m.mc_id = d.mc_id
        LEFT JOIN spell_mst sp ON sp.spell_id = d.spell_id
        WHERE d.tran_date = %s AND d.branch_id = %s
        GROUP BY d.mc_id, m.short_name, m.shed_type, m.drg_type, d.spell_id, sp.spell_name
        ORDER BY m.shed_type, m.drg_type, m.short_name, d.spell_id
    """, (date_str, branch_id))
    raw = cur.fetchall()
    cur.close(); db.close()

    machines = {}   # key -> accumulator (dict preserves insertion = sorted order)
    for r in raw:
        key = (r['shed_type'] or '', r['drg_type'] or '', r['mc_name'] or '')
        m = machines.setdefault(key, {
            'mc_name': r['mc_name'] or '', 'shed_type': r['shed_type'] or '',
            'drg_type': r['drg_type'] or '', 'const': 0.0, 'o_units': 0.0, 'o_rh': 0.0,
            'shifts': {'A': [0.0, 0.0], 'B': [0.0, 0.0], 'C': [0.0, 0.0]},
        })
        units = float(r['units'] or 0)
        rh    = float(r['running_hours'] or 0)
        m['const'] = max(m['const'], float(r['const_meter'] or 0))
        m['o_units'] += units; m['o_rh'] += rh
        letter = _drawing_shift_letter(r['spell_name'])
        if letter in m['shifts']:
            m['shifts'][letter][0] += units
            m['shifts'][letter][1] += rh

    rows = []
    for m in machines.values():
        const = m['const']
        row = {'mc_name': m['mc_name'], 'shed_type': m['shed_type'], 'drg_type': m['drg_type']}
        for letter in ('A', 'B', 'C'):
            u, rh = m['shifts'][letter]
            row[letter.lower() + '_unit'] = u
            row[letter.lower() + '_eff']  = _drawing_eff(u, rh, const)
        row['o_unit'] = m['o_units']
        row['o_eff']  = _drawing_eff(m['o_units'], m['o_rh'], const)
        rows.append(row)
    return rows


_DRW_W_M, _DRW_W_N, _DRW_ROW_H = 63.0, 25.5, 6.0   # 63 + 8*25.5 = 267mm (A4 landscape)


def _drawing_row_cells(r):
    return [_hands_fmt(r['a_unit']), _hands_fmt(r['a_eff']),
            _hands_fmt(r['b_unit']), _hands_fmt(r['b_eff']),
            _hands_fmt(r['c_unit']), _hands_fmt(r['c_eff']),
            _hands_fmt(r['o_unit']), _hands_fmt(r['o_eff'])]


def _drawing_total_cells(acc):
    # Units are summable; efficiency is not, so eff columns stay blank on totals.
    return [_hands_fmt(acc['A']), '', _hands_fmt(acc['B']), '',
            _hands_fmt(acc['C']), '', _hands_fmt(acc['O']), '']


def _drawing_draw_header(pdf):
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(_DRW_W_M, _DRW_ROW_H, 'Machine', border=1, align='L')
    for label in ('Shift A', 'Shift B', 'Shift C', 'Overall'):
        pdf.cell(2 * _DRW_W_N, _DRW_ROW_H, label, border=1, align='C')
    pdf.ln(_DRW_ROW_H)
    pdf.cell(_DRW_W_M, _DRW_ROW_H, '', border=1)
    for _ in range(4):
        pdf.cell(_DRW_W_N, _DRW_ROW_H, 'Unit', border=1, align='C')
        pdf.cell(_DRW_W_N, _DRW_ROW_H, 'Eff %', border=1, align='C')
    pdf.ln(_DRW_ROW_H)


def _drawing_draw_row(pdf, label, cells, bold=False, fill=False):
    pdf.set_font('Helvetica', 'B' if bold else '', 8)
    pdf.cell(_DRW_W_M, _DRW_ROW_H, label, border=1, align='L', fill=fill)
    for c in cells:
        pdf.cell(_DRW_W_N, _DRW_ROW_H, c, border=1, align='R', fill=fill)
    pdf.ln(_DRW_ROW_H)


def build_drawing_pdf(disp_date, branch_name, rows, out_path):
    """Render the Drawing Efficiency Report PDF for one branch to out_path."""
    from fpdf import FPDF
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.set_margins(15, 12, 15)
    pdf.add_page()
    page_bottom = pdf.h - pdf.b_margin

    suffix = ('  -  %s' % branch_name) if branch_name else ''
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(_DRW_W_M + 8 * _DRW_W_N, 8,
             'DRAWING EFFICIENCY REPORT   Dated %s%s' % (disp_date, suffix),
             border=1, align='C')
    pdf.ln(8)
    _drawing_draw_header(pdf)

    grand = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'O': 0.0}
    cur_sec = None
    sub = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'O': 0.0}
    sec_label = ''

    def flush_subtotal():
        if cur_sec is not None:
            _drawing_draw_row(pdf, '  Sub Total - %s' % sec_label,
                              _drawing_total_cells(sub), bold=True)

    for r in rows:
        sec = (r['shed_type'], r['drg_type'])
        if sec != cur_sec:
            flush_subtotal()
            cur_sec = sec
            sub = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'O': 0.0}
            sec_label = ' / '.join(p for p in (r['shed_type'], r['drg_type']) if p) or 'Drawing'
            if pdf.get_y() + 3 * _DRW_ROW_H > page_bottom:
                pdf.add_page(); _drawing_draw_header(pdf)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(_DRW_W_M + 8 * _DRW_W_N, _DRW_ROW_H, sec_label, border=1,
                     align='L', fill=True)
            pdf.ln(_DRW_ROW_H)
        if pdf.get_y() + _DRW_ROW_H > page_bottom:
            pdf.add_page(); _drawing_draw_header(pdf)
        _drawing_draw_row(pdf, '   %s' % r['mc_name'], _drawing_row_cells(r))
        for k, col in (('A', 'a_unit'), ('B', 'b_unit'), ('C', 'c_unit'), ('O', 'o_unit')):
            sub[k] += r[col]; grand[k] += r[col]

    flush_subtotal()

    if pdf.get_y() + _DRW_ROW_H > page_bottom:
        pdf.add_page(); _drawing_draw_header(pdf)
    _drawing_draw_row(pdf, 'Total as per above', _drawing_total_cells(grand),
                      bold=True, fill=True)

    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, 'Prepared on : %s' % datetime.now().strftime('%d-%m-%Y %H:%M'),
             align='R')

    pdf.output(out_path)
    return out_path


def send_daily_drawing_report(report_date, recipients=None):
    """Build and email the Drawing Efficiency Report for report_date. One PDF per branch.

    recipients = explicit emails (per-recipient scheduler); None = all msg_for='DR'.
    """
    import tempfile
    from src.spg_report import active_branches

    date_str = report_date.strftime('%Y-%m-%d')
    disp_date = report_date.strftime('%d-%m-%Y')

    emails = [e for e in recipients if e] if recipients is not None else drawing_recipients()
    if not emails:
        print('Drawing report: no recipients; skipping', date_str)
        return

    for branch_id, branch_name in active_branches():
        try:
            rows = fetch_drawing_efficiency(date_str, branch_id)
        except Exception as ex:
            print('Drawing report: data fetch failed for branch', branch_id, ex)
            continue
        if not rows:
            print('Drawing report: no data for branch', branch_id, 'on', date_str, '- skipping')
            continue

        fname = 'Drawing_Efficiency_%s_%s.pdf' % (branch_id, date_str)
        out_path = os.path.join(tempfile.gettempdir(), fname)
        try:
            build_drawing_pdf(disp_date, branch_name, rows, out_path)
        except Exception as ex:
            print('Drawing report: PDF build failed for branch', branch_id, ex)
            continue

        caption = 'Drawing Efficiency Report %s%s' % (
            disp_date, (' - ' + branch_name) if branch_name else '')
        body = '%s\n\nPlease find the attached report.' % caption
        for email in emails:
            ok, info = send_document(email, out_path, subject=caption,
                                     body=body, filename=fname)
            print('Drawing report: branch', branch_id, '-> email to', email,
                  '->', 'OK' if ok else 'FAILED', '|', info)
        try:
            os.remove(out_path)
        except Exception:
            pass


_drawing_scheduler = None


def start_drawing_scheduler():
    """Start the Drawing Efficiency Report scheduler (per-recipient sch_times, msg_for='DR')."""
    global _drawing_scheduler
    if _drawing_scheduler is not None:
        return _drawing_scheduler
    from src.spg_report import start_report_scheduler
    _drawing_scheduler = start_report_scheduler('Drawing report', 'DR', send_daily_drawing_report, 'drawing')
    return _drawing_scheduler


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--hands-selfcheck":
        assert _hands_fmt(0) == '' and _hands_fmt(None) == '' and _hands_fmt('x') == ''
        assert _hands_fmt(5) == '5' and _hands_fmt(5.0) == '5' and _hands_fmt(2.5) == '2.50'
        r = {'thands_a': 1, 'hands_a': 2, 'thands_b': 3, 'hands_b': 0,
             'thands_c': 0, 'hands_c': 4}
        assert _hands_row_cells(r) == ['1', '2', '3', '', '', '4', '4', '6'], _hands_row_cells(r)
        acc = {}
        _hands_add(acc, r); _hands_add(acc, r)
        assert acc['thands_a'] == 2 and acc['hands_c'] == 8
        print('hands report self-check OK')
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--drawing-selfcheck":
        assert _drawing_eff(100, 8, 100) == 100.0      # target = 100/8*8 = 100
        assert _drawing_eff(50, 8, 100) == 50.0
        assert _drawing_eff(10, 0, 100) == 0.0 and _drawing_eff(10, 8, 0) == 0.0
        assert _drawing_shift_letter('Shift A') == 'A'
        assert _drawing_shift_letter('B spell') == 'B' and _drawing_shift_letter('xyz') == ''
        r = {'a_unit': 10, 'a_eff': 90.0, 'b_unit': 0, 'b_eff': 0,
             'c_unit': 5, 'c_eff': 50.0, 'o_unit': 15, 'o_eff': 70.0}
        assert _drawing_row_cells(r) == ['10', '90', '', '', '5', '50', '15', '70'], _drawing_row_cells(r)
        assert _drawing_total_cells({'A': 10, 'B': 0, 'C': 5, 'O': 15}) == \
            ['10', '', '', '', '5', '', '15', ''], _drawing_total_cells({'A': 10, 'B': 0, 'C': 5, 'O': 15})
        print('drawing report self-check OK')
        sys.exit(0)

    to = sys.argv[1] if len(sys.argv) > 1 else ""
    subject = sys.argv[2] if len(sys.argv) > 2 else "Test email"
    body = sys.argv[3] if len(sys.argv) > 3 else "This is a test."
    attachment = sys.argv[4] if len(sys.argv) > 4 else None

    ok, info = send_document(to, attachment, subject, body)
    print("SENT OK" if ok else "FAILED")
    print(info)
    sys.exit(0 if ok else 1)
