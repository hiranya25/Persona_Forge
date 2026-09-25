"""
Persona Forge - form backend (Python / Flask)

Receives the two forms from the static frontend ("Reach us" and "Join the
waitlist") and sends them to you by email through your own SMTP account.
This is the piece a static HTML site cannot do on its own: the browser
never sees your SMTP credentials, only this server does.

Run locally:
    python3 -m venv venv && source venv/bin/activate   (Windows: venv\\Scripts\\activate)
    pip install -r requirements.txt
    cp .env.example .env      # then fill in your real values
    python app.py

Deploy it anywhere that runs a long-lived Python process: Render, Railway,
Fly.io, PythonAnywhere, or a small VPS behind gunicorn + nginx.
See README.md in this folder for step-by-step instructions.
"""

import json
import os
import re
import smtplib
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Serverless platforms (Vercel, AWS Lambda, etc.) deploy this code to a
# read-only filesystem — only /tmp is writable, and even that doesn't
# persist between separate invocations. Writing to BASE_DIR there raises
# a PermissionError/OSError. /tmp at least won't crash the request; if
# /tmp isn't writable either (unusual), we fall back to BASE_DIR for local
# development, where it works fine and persists normally.
_tmp_dir = Path("/tmp")
WAITLIST_FILE = (_tmp_dir if _tmp_dir.exists() and os.access(_tmp_dir, os.W_OK) else BASE_DIR) / "waitlist.json"

# --- Configuration -----------------------------------------------------------
#
# None of this is required for the server to start. A missing or incomplete
# SMTP setup used to call sys.exit() here, which took down every route —
# including /api/health and the bare "/" — the moment any one variable was
# blank or mistyped. Now the server always starts; only the two routes that
# actually need to send email check for complete config first, and reply
# with a clear, non-crashing error if it's missing.

REQUIRED_ENV_VARS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "OWNER_EMAIL"]
MISSING_ENV_VARS = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
if MISSING_ENV_VARS:
    print(
        "Warning: missing environment variable(s): " + ", ".join(MISSING_ENV_VARS)
        + ". The server will still start — /api/health and the frontend keep working —"
        + " but /api/contact and /api/waitlist will return a clear error instead of sending"
        + " email until these are set. Copy .env.example to .env and fill in your real"
        + " SMTP details, or set them in your hosting platform's environment variables.",
        file=sys.stderr,
    )

PORT = int(os.getenv("PORT", "4000"))
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
_smtp_port_raw = os.getenv("SMTP_PORT", "")
SMTP_PORT = int(_smtp_port_raw) if _smtp_port_raw.isdigit() else None
SMTP_SECURE = os.getenv("SMTP_SECURE", "false").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")


def smtp_configured() -> bool:
    return not MISSING_ENV_VARS

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# --- App setup ---------------------------------------------------------------

app = Flask(__name__)
CORS(app, origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else [], methods=["GET", "POST"])

# Very small in-memory rate limiter: N requests per IP per minute.
RATE_LIMIT = 6
RATE_WINDOW_SECONDS = 60
_hits = defaultdict(deque)


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW_SECONDS
    hits = _hits[ip]
    while hits and hits[0] < window_start:
        hits.popleft()
    hits.append(now)
    return len(hits) > RATE_LIMIT


def clean(value, max_len=2000) -> str:
    return str(value or "").strip()[:max_len]


def is_spam(body: dict) -> bool:
    """Honeypot field: real visitors never fill this in (it's hidden via CSS)."""
    return bool(clean(body.get("hp_website")))


def send_email(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = OWNER_EMAIL

    if SMTP_SECURE:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [OWNER_EMAIL], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [OWNER_EMAIL], msg.as_string())


def append_to_waitlist(email: str) -> None:
    entries = []
    if WAITLIST_FILE.exists():
        try:
            entries = json.loads(WAITLIST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []

    if not any(entry.get("email") == email for entry in entries):
        entries.append({"email": email, "joinedAt": datetime.now(timezone.utc).isoformat()})
        WAITLIST_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


# --- Routes -------------------------------------------------------------------

@app.route("/api/contact", methods=["POST"])
def contact():
    if is_rate_limited(request.remote_addr):
        return jsonify(ok=False, error="Too many requests. Try again in a minute."), 429

    body = request.get_json(silent=True) or {}
    if is_spam(body):
        return jsonify(ok=True)  # silently drop likely-bot submissions

    name = clean(body.get("name"), 200)
    company = clean(body.get("company"), 200)
    note = clean(body.get("note"), 4000)

    if not name or not company or not note:
        return jsonify(ok=False, error="Name, company, and note are all required."), 400

    if not smtp_configured():
        app.logger.warning("contact form received but SMTP is not configured — see MISSING_ENV_VARS")
        return jsonify(ok=False, error="Email sending isn't configured on this server yet."), 503

    try:
        send_email(
            subject=f"Design partner inquiry - {company}",
            body=f"Name: {name}\nCompany: {company}\n\n{note}",
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a generic failure
        app.logger.error("contact form error: %s", exc)
        return jsonify(ok=False, error="Could not send right now. Please try again shortly."), 500

    return jsonify(ok=True)


@app.route("/api/waitlist", methods=["POST"])
def waitlist():
    if is_rate_limited(request.remote_addr):
        return jsonify(ok=False, error="Too many requests. Try again in a minute."), 429

    body = request.get_json(silent=True) or {}
    if is_spam(body):
        return jsonify(ok=True)

    email = clean(body.get("email"), 200)
    if not EMAIL_RE.match(email):
        return jsonify(ok=False, error="Enter a valid email address."), 400

    # Saving to the local list is a nice-to-have, not the point of this
    # endpoint — the email notification is. On a serverless platform the
    # file write may fail or simply not persist; that alone should never
    # stop the email from going out, so it's isolated in its own try block.
    try:
        append_to_waitlist(email)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("waitlist file write failed (non-fatal): %s", exc)

    if not smtp_configured():
        app.logger.warning("waitlist signup received but SMTP is not configured — see MISSING_ENV_VARS")
        return jsonify(ok=False, error="Email sending isn't configured on this server yet."), 503

    try:
        send_email(subject="New waitlist signup", body=f"New waitlist signup: {email}")
    except Exception as exc:  # noqa: BLE001
        app.logger.error("waitlist email send failed: %s", exc)
        return jsonify(ok=False, error="Could not send right now. Please try again shortly."), 500

    return jsonify(ok=True)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(ok=True, smtp_configured=smtp_configured())


@app.route("/", methods=["GET"])
def index():
    # A plain, friendly status page instead of Flask's generic "Not Found" —
    # this backend has no root page of its own; the actual website is the
    # separate static frontend project.
    return jsonify(
        ok=True,
        service="Persona Forge form backend",
        smtp_configured=smtp_configured(),
        missing_env_vars=MISSING_ENV_VARS,
        endpoints=["/api/health", "/api/contact", "/api/waitlist"],
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
