# SPG Daily Report — Email Delivery

**Date:** 2026-06-15
**Status:** Approved (design)

## Summary

Deliver the existing per-branch *Spinning & Winding Production Summary* PDF by
**email** instead of WhatsApp. Recipients come from `tbl_whatsapp_send` where
`msg_for = 'SR'`, using the table's `email_id` column. The send runs on the
existing schedule — 07:00 (previous day), 15:00, and 23:00 server local time,
i.e. the requested 7am / 3pm / 11pm cadence. No scheduler changes are needed;
only the delivery channel changes from WhatsApp to email.

## Scope

In scope:
- New SMTP email sender module.
- Switch `spg_report.py`'s delivery from WhatsApp to email.
- `.env` SMTP configuration.
- A manual email-send test script.

Out of scope:
- Changing the report content, queries, or PDF layout.
- Changing the schedule times or scheduler wiring (`app.py`, `start_scheduler`).
- Removing `src/send_whatsapp.py` (kept on disk, simply no longer called by the
  report).

## Components

### 1. `src/send_email.py` (new)

Stdlib-only SMTP sender (`smtplib` + `email.message.EmailMessage`) — no new pip
dependency. Mirrors the shape of `src/send_whatsapp.py`.

- `_load_dotenv(filename=".env")` — reuse the same dotenv loader used by
  `send_whatsapp.py` (reads `.env` one directory above `src/`).
- `send_document(to_email, file_path, subject, body, filename) -> (ok, info)`
  - Reads SMTP config from the environment on each call (so `.env` edits take
    effect without re-import), with sensible defaults.
  - Builds an `EmailMessage`: `From` = `SMTP_FROM` or `SMTP_USER`, `To` =
    `to_email`, `Subject` = subject, plain-text body, PDF attached as
    `application/pdf` with the given `filename`.
  - Connects to `SMTP_HOST:SMTP_PORT`, issues `STARTTLS`, logs in with
    `SMTP_USER` / `SMTP_PASSWORD`, sends.
  - Returns `(True, "OK")` on success or `(False, "<reason>")` on any
    exception. Never raises to the caller.
  - Guards: if `SMTP_USER`/`SMTP_PASSWORD` are unset, returns
    `(False, "SMTP not configured ...")`.

### 2. `.env` additions

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tarunksadhukhan2@gmail.com
SMTP_PASSWORD=        # Gmail App Password (16 chars, spaces removed)
SMTP_FROM=            # optional; defaults to SMTP_USER
```

Defaults in code: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`.

### 3. `src/spg_report.py` changes

- **Module docstring** — update the channel description from WhatsApp to email.
- **Import** — replace `from src.send_whatsapp import send_document` with
  `from src.send_email import send_document`.
- **`report_recipients()`** — add `email_id` to the SELECT (the requested schema
  update). Keep `WHERE msg_for = 'SR'`. Returns rows with
  `name, mobno, from_msg, email_id`.
- **`send_daily_spg_report(report_date)`**:
  - Replace the mobile-number collection (`_wa_clean_number`) with collection of
    distinct, non-blank, trimmed `email_id` values. If none, log and return.
  - For each active branch PDF, loop over the email list and call
    `send_email.send_document(email, out_path, subject, body, filename)`.
    - `subject` = the existing caption string
      (`"Spinning & Winding Production Summary <dd-mm-YYYY>[ - <branch>]"`).
    - `body` = a short line, e.g. the caption plus "Please find the attached
      report."
  - Preserve per-recipient `OK`/`FAILED | <info>` logging and the temp-file
    cleanup.
- **`_wa_clean_number`** — remove (dead once email-only).

### 4. `test_send_email.py` (new, repo root, sibling to `test_spg_report.py`)

Builds the report PDF for one branch (yesterday or a CLI date) and emails it to a
single address given on the command line, e.g.:

```
python test_send_email.py you@example.com 2026-06-11
```

Verifies SMTP works end to end without touching the schedule or the full
recipient list.

## Data Flow

```
scheduler (07:00 prev / 15:00 / 23:00)
  -> send_daily_spg_report(date)
       -> report_recipients()        # tbl_whatsapp_send, msg_for='SR', email_id
       -> for each active branch:
            fetch_* queries -> build_report_pdf -> /tmp/SPG_Summary_<branch>_<date>.pdf
            -> for each email_id: send_email.send_document(...)  -> log OK/FAILED
            -> remove temp PDF
```

## Error Handling

- SMTP errors are caught inside `send_document` and returned as
  `(False, reason)`; the report loop logs `FAILED | <reason>` and continues —
  one bad recipient or transient SMTP error does not abort the run.
- Missing SMTP credentials short-circuit each send with a clear message.
- No recipients / no valid emails -> log and return (same as the existing
  no-recipients guard).

## Testing

- `test_send_email.py` for a manual end-to-end check to one address.
- Existing `test_spg_report.py` continues to validate PDF building (unchanged).

## Configuration Reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `SMTP_HOST` | SMTP server | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port (STARTTLS) | `587` |
| `SMTP_USER` | SMTP login / sender | — (required) |
| `SMTP_PASSWORD` | SMTP password / Gmail App Password | — (required) |
| `SMTP_FROM` | From address | falls back to `SMTP_USER` |
| `SPG_REPORT_TIMES` | current-date run times | `15:00,23:00` (unchanged) |
| `SPG_REPORT_TIMES_PREVDAY` | previous-date run times | `07:00` (unchanged) |
| `SPG_REPORT_BRANCHES` | branch id filter | `103` (unchanged) |
