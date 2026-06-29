"""MIS Report — multi-period production summary as a scheduled-email PDF.

Ported from the sjmvowerp3be FastAPI module (src/misReports/misReport.py) to this
Flask + mysql.connector project, kept SEPARATE from send_email.py (it only reuses
send_email.send_document to actually post the mail).

Period layout derived from ``as_of_date`` (e.g. 2026-05-23):
    P1: as_of .. as_of                 (selected date)
    P2: first_of_current_month .. as_of (MTD)
    P3..P7: previous 5 full months (newest first)
    P8: Total = sum of P2..P7 (excludes P1 so MTD isn't double-counted)

Only metrics with a known data source are populated; the rest render blank so the
layout matches the source PDF. Each source query is defensive: a missing column /
table blanks that metric instead of failing the whole report.

Schedule (server local time, env-configurable):
    MIS_REPORT_TIMES         -> report for the CURRENT date  (default 23:00)
    MIS_REPORT_TIMES_PREVDAY -> report for the PREVIOUS date (default 08:00)
Recipients: tbl_whatsapp_send rows with msg_for = MIS_REPORT_MSG_FOR (default 'MIS').
"""
import os
import calendar
import tempfile
from datetime import date, datetime, timedelta

from fpdf import FPDF

from db import get_db
from src.send_email import send_document

NUM_PERIODS = 8
TOTAL_COL_INDEX = NUM_PERIODS - 1   # last column is the computed Total
TOTAL_SUM_START_INDEX = 1           # Total = sum of cols 1..6 (MTD + prev 5 months)
TRAN_TYPE_PURCHASE = 1
TRAN_TYPE_SALES = 2


# -- periods ------------------------------------------------------------------

def _shift_month(d, delta_months):
    """First-of-month shifted by delta_months from d."""
    total = d.year * 12 + (d.month - 1) + delta_months
    y, m = divmod(total, 12)
    return date(y, m + 1, 1)


def build_periods(as_of):
    """Return 8 period dicts: [selected date, MTD, prev-5-months..., Total]."""
    periods = []
    periods.append({'from': as_of, 'to': as_of, 'is_total': False,
                    'sub': '%s to %s' % (as_of.strftime('%d-%m-%Y'), as_of.strftime('%d-%m-%Y'))})
    p2_from = as_of.replace(day=1)
    periods.append({'from': p2_from, 'to': as_of, 'is_total': False,
                    'sub': '%s to %s' % (p2_from.strftime('%d-%m-%Y'), as_of.strftime('%d-%m-%Y'))})
    for i in range(1, 6):
        first = _shift_month(as_of.replace(day=1), -i)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        periods.append({'from': first, 'to': last, 'is_total': False,
                        'sub': '%s to %s' % (first.strftime('%d-%m-%Y'), last.strftime('%d-%m-%Y'))})
    periods.append({'from': None, 'to': None, 'is_total': True, 'sub': 'Total'})
    return periods


def _apply_totals(sections):
    """values[TOTAL_COL_INDEX] = sum(values[1:TOTAL_COL_INDEX]) for every row."""
    for section in sections:
        for row in section['rows']:
            row['values'][TOTAL_COL_INDEX] = sum(
                row['values'][TOTAL_SUM_START_INDEX:TOTAL_COL_INDEX])


# -- db helpers ---------------------------------------------------------------

def _in_clause(n):
    return '(' + ','.join(['%s'] * n) + ')'


def _all_branch_ids():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT branch_id FROM branch_mst WHERE (active IS NULL OR active = 1) ORDER BY branch_id")
    ids = [int(r[0]) for r in cur.fetchall()]
    cur.close(); db.close()
    return ids


def _company_name():
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT co_name FROM co_mst ORDER BY co_id LIMIT 1")
        row = cur.fetchone()
        cur.close(); db.close()
        return (row[0] if row and row[0] else 'Company')
    except Exception:
        return 'Company'


def _periods_scalar(branch_ids, periods, sql_tmpl, extra_params=lambda p: ()):
    """Run a single-scalar SQL per period; return [float]*NUM_PERIODS.

    sql_tmpl uses '{in}' for the branch IN clause; params are branch_ids then
    whatever extra_params(period) yields. Defensive: any error -> all zeros.
    """
    result = [0.0] * NUM_PERIODS
    if not branch_ids:
        return result
    sql = sql_tmpl.format(**{'in': _in_clause(len(branch_ids))})
    try:
        db = get_db()
        cur = db.cursor()
        for idx, p in enumerate(periods):
            if p['is_total']:
                continue
            cur.execute(sql, tuple(branch_ids) + tuple(extra_params(p)))
            row = cur.fetchone()
            result[idx] = float((row[0] if row else 0) or 0)
        cur.close(); db.close()
    except Exception as ex:
        print('MIS report: source query failed:', ex)
    return result


# -- source queries -----------------------------------------------------------

def _other_entries_aggregates(branch_ids, periods):
    keys = ('elec_unit', 'dg_unit', 'wip_data', 'dust_boiler')
    result = {k: [0.0] * NUM_PERIODS for k in keys}
    if not branch_ids:
        return result
    sql = ("SELECT COALESCE(SUM(elec_unit),0), COALESCE(SUM(dg_unit),0), "
           "COALESCE(SUM(wip_data),0), COALESCE(SUM(dust_boiler),0) "
           "FROM tbl_other_entries WHERE branch_id IN %s AND tran_date BETWEEN %s AND %s"
           % (_in_clause(len(branch_ids)), '%s', '%s'))
    try:
        db = get_db(); cur = db.cursor()
        for idx, p in enumerate(periods):
            if p['is_total']:
                continue
            cur.execute(sql, tuple(branch_ids) + (p['from'], p['to']))
            row = cur.fetchone()
            if row:
                for k, v in zip(keys, row):
                    result[k][idx] = float(v or 0)
        cur.close(); db.close()
    except Exception as ex:
        print('MIS report: other_entries failed:', ex)
    return result


def _jute_received_totals(branch_ids, periods):
    return _periods_scalar(
        branch_ids, periods,
        "SELECT COALESCE(SUM(weight),0) FROM tbl_jute_received "
        "WHERE branch_id IN {in} AND recv_date BETWEEN %s AND %s",
        lambda p: (p['from'], p['to']))


def _jute_issued_totals(branch_ids, periods):
    return _periods_scalar(
        branch_ids, periods,
        "SELECT COALESCE(SUM(net_wt),0) FROM assorting_entry "
        "WHERE branch_id IN {in} AND entry_date BETWEEN %s AND %s",
        lambda p: (p['from'], p['to']))


def _opening_with_double_in(branch_ids, periods):
    """Opening = received − issued strictly before each period start.

    Two IN clauses -> branch_ids must be passed twice, plus the two dates.
    """
    result = [0.0] * NUM_PERIODS
    if not branch_ids:
        return result
    inc = _in_clause(len(branch_ids))
    sql = ("SELECT (SELECT COALESCE(SUM(weight),0) FROM tbl_jute_received "
           "          WHERE branch_id IN %s AND recv_date < %s) "
           "     - (SELECT COALESCE(SUM(net_wt),0) FROM assorting_entry "
           "          WHERE branch_id IN %s AND entry_date < %s)"
           % (inc, '%s', inc, '%s'))
    try:
        db = get_db(); cur = db.cursor()
        for idx, p in enumerate(periods):
            if p['is_total']:
                continue
            cur.execute(sql, tuple(branch_ids) + (p['from'],) + tuple(branch_ids) + (p['from'],))
            row = cur.fetchone()
            result[idx] = float((row[0] if row else 0) or 0)
        cur.close(); db.close()
    except Exception as ex:
        print('MIS report: jute_opening failed:', ex)
    return result


def _hands_totals(branch_ids, periods):
    return _periods_scalar(
        branch_ids, periods,
        "SELECT COALESCE(SUM(working_hours - COALESCE(idle_hours,0)),0)/8 "
        "FROM daily_attendance WHERE branch_id IN {in} "
        "AND COALESCE(is_active,1)=1 AND attendance_date BETWEEN %s AND %s",
        lambda p: (p['from'], p['to']))


def _daily_finishing_totals(periods):
    """branding/bales/issue_bales/cuts/pack_sheet per period (no branch column)."""
    keys = ('branding', 'bales', 'issue_bales', 'cuts', 'pack_sheet')
    result = {k: [0.0] * NUM_PERIODS for k in keys}
    sql = ("SELECT COALESCE(SUM(branding),0), COALESCE(SUM(bales),0), "
           "COALESCE(SUM(issue_bales),0), COALESCE(SUM(cuts),0), COALESCE(SUM(pack_sheet),0) "
           "FROM tbl_daily_finishing WHERE tran_date BETWEEN %s AND %s")
    try:
        db = get_db(); cur = db.cursor()
        for idx, p in enumerate(periods):
            if p['is_total']:
                continue
            cur.execute(sql, (p['from'], p['to']))
            row = cur.fetchone()
            if row:
                for k, v in zip(keys, row):
                    result[k][idx] = float(v or 0)
        cur.close(); db.close()
    except Exception as ex:
        print('MIS report: daily_finishing failed:', ex)
    return result


def _by_quality(branch_ids, periods, sql_tmpl, params_fn):
    """Generic {quality_name: [period values]} builder. Defensive -> {} on error."""
    out = {}
    if not branch_ids:
        return out
    sql = sql_tmpl.format(**{'in': _in_clause(len(branch_ids))})
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        for idx, p in enumerate(periods):
            if p['is_total']:
                continue
            cur.execute(sql, tuple(branch_ids) + tuple(params_fn(p)))
            for r in cur.fetchall():
                name = r['quality_name'] or '(unknown)'
                out.setdefault(name, [0.0] * NUM_PERIODS)
                out[name][idx] = float(r['total_weight'] or 0)
        cur.close(); db.close()
    except Exception as ex:
        print('MIS report: quality query failed:', ex)
    return out


def _mill_production_by_quality(branch_ids, periods):
    return _by_quality(
        branch_ids, periods,
        "SELECT COALESCE(sq.spg_quality, CONCAT('Quality #', d.quality_id), '(unknown)') AS quality_name, "
        "       COALESCE(SUM(d.net_weight),0) AS total_weight "
        "FROM daily_doff_tbl d "
        "LEFT JOIN spinning_quality_mst sq ON sq.spg_quality_mst_id = d.quality_id "
        "WHERE d.branch_id IN {in} AND COALESCE(d.active,1)=1 "
        "AND d.doff_date BETWEEN %s AND %s "
        "GROUP BY quality_name",
        lambda p: (p['from'], p['to']))


def _yarn_by_type(branch_ids, periods, tran_type):
    return _by_quality(
        branch_ids, periods,
        "SELECT COALESCE(sq.spg_quality, CONCAT('Quality #', y.quality_id)) AS quality_name, "
        "       COALESCE(SUM(y.weight),0) AS total_weight "
        "FROM tbl_yarn_transaction y "
        "LEFT JOIN spinning_quality_mst sq ON sq.spg_quality_mst_id = y.quality_id "
        "WHERE y.branch_id IN {in} AND y.tran_type = %s AND y.tran_date BETWEEN %s AND %s "
        "GROUP BY quality_name",
        lambda p: (tran_type, p['from'], p['to']))


# -- sections -----------------------------------------------------------------

def _zeros():
    return [0.0] * NUM_PERIODS


def _row(sl, label, values=None):
    return {'sl_no': sl, 'label': label, 'values': values if values is not None else _zeros()}


def build_sections(branch_ids, periods):
    other = _other_entries_aggregates(branch_ids, periods)
    yarn_purchases = _yarn_by_type(branch_ids, periods, TRAN_TYPE_PURCHASE)
    yarn_sales = _yarn_by_type(branch_ids, periods, TRAN_TYPE_SALES)
    raw_arrival = _jute_received_totals(branch_ids, periods)
    raw_issued = _jute_issued_totals(branch_ids, periods)
    raw_opening = _opening_with_double_in(branch_ids, periods)
    raw_closing = [raw_opening[i] + raw_arrival[i] - raw_issued[i] for i in range(NUM_PERIODS)]
    fin = _daily_finishing_totals(periods)
    branded_kgs = [v * 290 for v in fin['bales']]
    sales_branded_kgs = [v * 290 for v in fin['issue_bales']]
    fabrics_kgs = [v * 30.2467 for v in fin['cuts']]
    pack_sheet_kgs = [v * 39 for v in fin['pack_sheet']]
    mill = _mill_production_by_quality(branch_ids, periods)
    hands = _hands_totals(branch_ids, periods)

    purchase_totals = _zeros()
    for vals in yarn_purchases.values():
        for i, v in enumerate(vals):
            purchase_totals[i] += v

    sections = []

    # 1. Raw Jute Report
    rows = [_row(1, 'Raw Jute Arrival (in Kgs)', raw_arrival),
            _row(2, 'Yarns/Fabrics Purchased (in Kgs)', purchase_totals)]
    for q in sorted(yarn_purchases.keys()):
        rows.append(_row('', '    %s (in Kgs)' % q, yarn_purchases[q]))
    rows += [_row(3, 'Raw Jute Issued (in Kgs)', raw_issued),
             _row(4, 'Raw Jute Closing Stock (in Kgs)', raw_closing)]
    sections.append({'title': 'Raw Jute Report', 'rows': rows})

    # 2. Finished Goods Stock
    sections.append({'title': 'Finished Goods Stock', 'rows': [
        _row(1, 'Branded Bags (in Kgs)', branded_kgs),
        _row(2, 'Branded Bags (in Bales)', fin['bales'])]})

    # 3. Sales Summary
    rows = [_row(1, 'Branded Bags (in Kgs)', sales_branded_kgs),
            _row(2, 'Branded Bags (in Bales)', fin['issue_bales'])]
    for i, q in enumerate(sorted(yarn_sales.keys()), start=3):
        rows.append(_row(i, '%s (in Kgs)' % q, yarn_sales[q]))
    sections.append({'title': 'Sales Summary', 'rows': rows})

    # 4. Stock Summary (WIP + Dust real; rest placeholder)
    sections.append({'title': 'Stock Summary', 'rows': [
        _row(1, 'Opening Stock'), _row(2, 'Input'), _row(3, 'Sales'),
        _row(4, 'Jute Loss on Output 9%'), _row(5, 'Closing Stock'),
        _row(6, 'Ready Stock of Raw+Finished'),
        _row(7, 'WIP', other['wip_data']),
        _row(8, 'Dust to Boiler', other['dust_boiler'])]})

    # 5. Mill Production Summary
    rows = []
    total_mill = _zeros()
    for i, q in enumerate(sorted(mill.keys()), start=1):
        vals = mill[q]
        for j, v in enumerate(vals):
            total_mill[j] += v
        rows.append(_row(i, q, vals))
    nxt = len(rows) + 1
    rows.append(_row('', 'Total Mill Shed Production', total_mill))
    rows.append(_row(nxt, 'Fabrics', fabrics_kgs))
    rows.append(_row(nxt + 1, 'Pack Sheet', pack_sheet_kgs))
    rows.append(_row(nxt + 2, 'Stiched Bags'))
    rows.append(_row(nxt + 3, 'Branded Bags', fin['branding']))
    sections.append({'title': 'Mill Production Summary', 'rows': rows})

    # 6. Analytical Report (hands / elec / DG real; rest placeholder)
    sections.append({'title': 'Analytical Report', 'rows': [
        _row(1, 'Hands', hands), _row(2, 'Hands per Ton'), _row(3, 'Hands per Frame'),
        _row(4, 'Wages'), _row(5, 'Wages Per ton'),
        _row(6, 'Electricity Units', other['elec_unit']),
        _row(7, 'DG Units', other['dg_unit']),
        _row(8, 'Units per ton'), _row(9, 'No. of Frames run'),
        _row(10, 'Per Frames Production')]})

    # 7 & 8. Mill Production New/Old Shed (needs mc->shed map; placeholder labels)
    q_labels = sorted(mill.keys())
    new_rows = [_row(i + 1, lbl) for i, lbl in enumerate(q_labels)]
    new_rows.append(_row('', 'Total Mill Shed Production'))
    sections.append({'title': 'Mill Production Summary (in New Shed)',
                     'rows': new_rows, 'page_break_before': True})
    old_rows = [_row(i + 1, lbl) for i, lbl in enumerate(q_labels)]
    old_rows.append(_row('', 'Total Mill Shed Production'))
    sections.append({'title': 'Mill Production Summary (in Old Shed)', 'rows': old_rows})

    # 9. Factory Production Summary
    sections.append({'title': 'Factory Production Summary', 'rows': [
        _row(1, 'Fabrics (in Bags) (assumed 57/roll)'),
        _row(2, 'Pack Sheet (in Bags)'), _row(3, 'Cutting (in Bags)'),
        _row(4, 'Heming (in Bags)'), _row(5, 'Hiracle (in Bags)'),
        _row(6, 'Branded Bags', fin['branding']),
        _row(7, 'Bales (of 500 Bags)', fin['bales'])]})

    # 10. Target Production (config table TODO)
    sections.append({'title': 'Target Production', 'rows': [
        _row(1, 'Mill Production'), _row(2, 'Factory Production'),
        _row(3, 'Finishing Production')]})

    _apply_totals(sections)
    return sections


def build_mis_report_data(report_date):
    """Return the full report dict {company_name, as_of_date, periods, sections}."""
    branch_ids = _all_branch_ids()
    periods = build_periods(report_date)
    sections = build_sections(branch_ids, periods)
    return {
        'company_name': _company_name(),
        'as_of_date': report_date.strftime('%Y-%m-%d'),
        'periods': [{'sub': p['sub']} for p in periods],
        'sections': sections,
    }


# -- pdf (fpdf2, mirrors the reportlab layout: green header, orange sections) --

_GREEN = (183, 225, 205)    # #B7E1CD header band
_ORANGE = (252, 229, 205)   # #FCE5CD section band


def _fmt_num(v):
    """Thousands-separated, up to 2dp, trailing zeros trimmed; blank for 0/None."""
    if not v:
        return ''
    s = '{:,.2f}'.format(v).rstrip('0').rstrip('.')
    return s


def build_mis_pdf(report, out_path):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.set_margins(8, 8, 8)
    pdf.add_page()
    page_bottom = pdf.h - pdf.b_margin

    avail = pdf.w - pdf.l_margin - pdf.r_margin   # ~281mm
    n_cols = len(report['periods'])               # 8 (7 dates + Total)
    w_sl, w_part = 10.0, 51.0
    w_p = (avail - w_sl - w_part) / n_cols
    widths = [w_sl, w_part] + [w_p] * n_cols
    row_h = 5.0
    headers = ['Sl.No', 'Particulars'] + [p['sub'] for p in report['periods']]

    def heading():
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(avail, 7, report['company_name'], align='C')
        pdf.ln(7)
        pdf.set_font('Helvetica', 'BI', 10)
        pdf.cell(avail, 5, 'MIS Report - As of %s' % report['as_of_date'], align='L')
        pdf.ln(7)

    def col_header():
        pdf.set_font('Helvetica', 'B', 6)
        pdf.set_fill_color(*_GREEN)
        for w, h in zip(widths, headers):
            pdf.cell(w, row_h, h, border=1, align='C', fill=True)
        pdf.ln(row_h)

    heading()
    col_header()

    for section in report['sections']:
        if section.get('page_break_before'):
            pdf.add_page(); heading(); col_header()
        # Section band (spans full width).
        if pdf.get_y() + 2 * row_h > page_bottom:
            pdf.add_page(); col_header()
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_fill_color(*_ORANGE)
        pdf.cell(avail, row_h, section['title'], border=1, align='L', fill=True)
        pdf.ln(row_h)

        for r in section['rows']:
            if pdf.get_y() + row_h > page_bottom:
                pdf.add_page(); col_header()
            pdf.set_font('Helvetica', '', 6)
            pdf.cell(w_sl, row_h, str(r['sl_no']), border=1, align='C')
            pdf.cell(w_part, row_h, r['label'], border=1, align='L')
            for v in r['values']:
                pdf.cell(w_p, row_h, _fmt_num(v), border=1, align='R')
            pdf.ln(row_h)

    pdf.output(out_path)
    return out_path


# -- send ---------------------------------------------------------------------

def mis_recipients():
    """Distinct email_ids from tbl_whatsapp_send where msg_for = MIS_REPORT_MSG_FOR."""
    code = os.getenv('MIS_REPORT_MSG_FOR', 'MIS').strip() or 'MIS'
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


def send_daily_mis_report(report_date, recipients=None):
    """Build the company-wide MIS Report PDF for report_date and email it.

    recipients = explicit emails (per-recipient scheduler); None = all msg_for='MIS'.
    """
    date_str = report_date.strftime('%Y-%m-%d')
    emails = [e for e in recipients if e] if recipients is not None else mis_recipients()
    if not emails:
        print('MIS report: no recipients; skipping', date_str)
        return

    try:
        report = build_mis_report_data(report_date)
    except Exception as ex:
        print('MIS report: data build failed:', ex)
        return

    fname = 'mis_report_%s.pdf' % date_str
    out_path = os.path.join(tempfile.gettempdir(), fname)
    try:
        build_mis_pdf(report, out_path)
    except Exception as ex:
        print('MIS report: PDF build failed:', ex)
        return

    caption = 'MIS Report - As of %s' % report_date.strftime('%d-%m-%Y')
    body = '%s\n\nPlease find the attached report.' % caption
    for email in emails:
        ok, info = send_document(email, out_path, subject=caption, body=body, filename=fname)
        print('MIS report: email to', email, '->', 'OK' if ok else 'FAILED', '|', info)
    try:
        os.remove(out_path)
    except Exception:
        pass


# -- scheduler ----------------------------------------------------------------

_scheduler = None


def start_mis_scheduler():
    """Start the MIS Report scheduler. Times from tbl_whatsapp_send.sch_times
    (msg_for='MIS'). Idempotent per process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    from src.spg_report import start_report_scheduler
    _scheduler = start_report_scheduler('MIS report', 'MIS', send_daily_mis_report, 'mis')
    return _scheduler


if __name__ == '__main__':
    # Pure-logic self-check (no DB).
    as_of = date(2026, 5, 23)
    ps = build_periods(as_of)
    assert len(ps) == NUM_PERIODS
    assert ps[0]['from'] == as_of and ps[0]['to'] == as_of
    assert ps[1]['from'] == date(2026, 5, 1) and ps[1]['to'] == as_of
    assert ps[2]['from'] == date(2026, 4, 1) and ps[2]['to'] == date(2026, 4, 30)
    assert ps[6]['from'] == date(2025, 12, 1) and ps[6]['to'] == date(2025, 12, 31)
    assert ps[7]['is_total']
    secs = [{'rows': [{'values': [300, 26400, 22152, 10060, 0, 0, 0, 0]}]}]
    _apply_totals(secs)
    assert secs[0]['rows'][0]['values'][TOTAL_COL_INDEX] == 58612, secs[0]['rows'][0]['values']
    assert _fmt_num(0) == '' and _fmt_num(None) == ''
    assert _fmt_num(26400) == '26,400' and _fmt_num(5595.64) == '5,595.64' and _fmt_num(1139.5) == '1,139.5'
    print('mis_report self-check OK')
