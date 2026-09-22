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
WAITLIST_FILE = BASE_DIR / "waitlist.json"

# --- Required configuration -------------------------------------------------

REQUIRED_ENV_VARS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "OWNER_EMAIL"]
missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
if missing:
    print(
        "Missing required environment variable(s): "
        + ", ".join(missing)
        + "\nCopy .env.example to .env and fill in your real SMTP details before starting the server.",
        file=sys.stderr,
    )
    sys.exit(1)

PORT = int(os.getenv("PORT", "4000"))
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_SECURE = os.getenv("SMTP_SECURE", "false").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
OWNER_EMAIL = os.getenv("OWNER_EMAIL")

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

    try:
        append_to_waitlist(email)
        send_email(subject="New waitlist signup", body=f"New waitlist signup: {email}")
    except Exception as exc:  # noqa: BLE001
        app.logger.error("waitlist form error: %s", exc)
        return jsonify(ok=False, error="Could not save that right now. Please try again shortly."), 500

    return jsonify(ok=True)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
