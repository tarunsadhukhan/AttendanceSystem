"""WhatsApp sender (Meta Cloud API).

Sends a single text message. No external packages required (uses urllib).
Reads credentials from the project-root .env file (or environment variables).

Usage:
    python -m src.send_whatsapp
    python -m src.send_whatsapp 919874337485 "Record Saved"
"""
import os
import sys
import json
import urllib.request
import urllib.error


def _load_dotenv(filename=".env"):
    """Load KEY=VALUE lines from the project-root .env into os.environ (no deps).

    send_whatsapp.py lives in src/, so the .env is one directory up.
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
ACCESS_TOKEN    = os.getenv("WHATSAPP_TOKEN", "PASTE_YOUR_TOKEN_HERE")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1065035110035891")
API_VERSION     = os.getenv("WHATSAPP_API_VERSION", "v21.0")

DEFAULT_TO      = "919874337485"
DEFAULT_MESSAGE = "Record Saved"
# -----------------------------------------------------------------------------


def send_text(to, body):
    """Send a plain-text WhatsApp message. Returns (ok, response_text).

    Re-reads the token from the environment on each call so a token updated in
    .env / the environment takes effect without re-importing the module.
    """
    token    = os.getenv("WHATSAPP_TOKEN", ACCESS_TOKEN)
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    version  = os.getenv("WHATSAPP_API_VERSION", API_VERSION)
    if not token or token == "PASTE_YOUR_TOKEN_HERE":
        return False, "No token set. Edit .env (WHATSAPP_TOKEN) or set the env var."

    url = "https://graph.facebook.com/%s/%s/messages" % (version, phone_id)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, str(e)


def _multipart_encode(fields, file_field, filename, content, ctype):
    """Build a multipart/form-data body (no external deps). Returns (boundary, body_bytes)."""
    boundary = "----SJMWhatsAppBoundary1a2b3c4d5e6f"
    crlf = b"\r\n"
    body = b""
    for key, val in fields.items():
        body += b"--" + boundary.encode() + crlf
        body += ('Content-Disposition: form-data; name="%s"' % key).encode() + crlf + crlf
        body += str(val).encode() + crlf
    body += b"--" + boundary.encode() + crlf
    body += ('Content-Disposition: form-data; name="%s"; filename="%s"'
             % (file_field, filename)).encode() + crlf
    body += ("Content-Type: %s" % ctype).encode() + crlf + crlf
    body += content + crlf
    body += b"--" + boundary.encode() + b"--" + crlf
    return boundary, body


def upload_media(file_path, mime="application/pdf"):
    """Upload a file to the Cloud API media endpoint. Returns (ok, media_id_or_error)."""
    token    = os.getenv("WHATSAPP_TOKEN", ACCESS_TOKEN)
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    version  = os.getenv("WHATSAPP_API_VERSION", API_VERSION)
    if not token or token == "PASTE_YOUR_TOKEN_HERE":
        return False, "No token set."
    try:
        with open(file_path, "rb") as fh:
            content = fh.read()
    except Exception as e:
        return False, "Cannot read file: %s" % e

    url = "https://graph.facebook.com/%s/%s/media" % (version, phone_id)
    boundary, body = _multipart_encode(
        {"messaging_product": "whatsapp", "type": mime},
        "file", os.path.basename(file_path), content, mime,
    )
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            mid = data.get("id")
            return (True, mid) if mid else (False, str(data))
    except urllib.error.HTTPError as e:
        return False, "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, str(e)


def send_document(to, file_path, caption=None, filename=None):
    """Send a PDF/document: uploads the file, then sends it. Returns (ok, info)."""
    ok, media_id = upload_media(file_path)
    if not ok:
        return False, "upload failed: " + str(media_id)

    token    = os.getenv("WHATSAPP_TOKEN", ACCESS_TOKEN)
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    version  = os.getenv("WHATSAPP_API_VERSION", API_VERSION)
    document = {"id": media_id, "filename": filename or os.path.basename(file_path)}
    if caption:
        document["caption"] = caption
    payload = {"messaging_product": "whatsapp", "to": to, "type": "document",
               "document": document}
    url = "https://graph.facebook.com/%s/%s/messages" % (version, phone_id)
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    to      = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TO
    message = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MESSAGE

    ok, info = send_text(to, message)
    print("SENT OK" if ok else "FAILED")
    print(info)
    sys.exit(0 if ok else 1)
