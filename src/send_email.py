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


if __name__ == "__main__":
    to = sys.argv[1] if len(sys.argv) > 1 else ""
    subject = sys.argv[2] if len(sys.argv) > 2 else "Test email"
    body = sys.argv[3] if len(sys.argv) > 3 else "This is a test."
    attachment = sys.argv[4] if len(sys.argv) > 4 else None

    ok, info = send_document(to, attachment, subject, body)
    print("SENT OK" if ok else "FAILED")
    print(info)
    sys.exit(0 if ok else 1)
