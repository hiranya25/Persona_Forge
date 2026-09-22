# Persona Forge — form backend (Python / Flask, your own SMTP)

This is the piece that lets "Reach us" and "Join the waitlist" actually
send email through your own SMTP account instead of opening the visitor's
email client. It's a small Flask app using Python's built-in `smtplib` —
it holds your SMTP credentials (the frontend never sees them) and exposes
two endpoints the static site calls.

## 1. Get your SMTP credentials

Any provider works — this is the same info you'd put into a mail client:

- **Your existing email host** (check its SMTP settings page)
- **Gmail** — use an [App Password](https://support.google.com/accounts/answer/185833),
  not your normal password (requires 2-Step Verification enabled).
  Host: `smtp.gmail.com`, Port: `587`, `SMTP_SECURE=false`
- **Outlook/Microsoft 365** — Host: `smtp.office365.com`, Port: `587`, `SMTP_SECURE=false`
- **Zoho Mail** — Host: `smtp.zoho.com`, Port: `587`, `SMTP_SECURE=false`
- **A transactional provider** (Resend, Postmark, SendGrid) — better
  deliverability at real volume; each gives you SMTP credentials in their
  dashboard, often on port `465` with `SMTP_SECURE=true`

## 2. Store your credentials safely

```bash
cd server
cp .env.example .env
```

Open `.env` and fill in your real SMTP host, port, username, password, and
the `OWNER_EMAIL` you want submissions delivered to.

**`.env` is already listed in `.gitignore`** — it will never be committed
to version control or bundled into a deployment by accident, as long as
you don't rename it. Treat it like a password file: don't paste its
contents into chat, screenshots, or public repos. If a credential ever
does leak, rotate it (generate a new app password / API key) rather than
just deleting the old file.

`app.py` also refuses to start if any required variable is missing, so a
half-filled `.env` fails loudly instead of silently sending nothing.

## 3. Install and run

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

It listens on `PORT` (default `4000`) and exposes:

- `POST /api/contact` — `{ name, company, note }` → emails you the "Reach us" submission
- `POST /api/waitlist` — `{ email }` → emails you a notification and appends the address to `waitlist.json`
- `GET /api/health` — returns `{ "ok": true }` if it's running

## 4. Point the frontend at it

In `../js/config.js`, set:

```js
formEndpoint: "https://your-deployed-backend-url",
```

Once set, both forms POST there and show a success message inline. Leave
`formEndpoint` empty and the frontend automatically falls back to opening
a `mailto:` link instead — the site works either way.

## 5. Deploying

This needs somewhere that keeps a Python process running (unlike the
static frontend, which can sit on any file host):

- **Render** or **Railway** — connect the `server/` folder as a Python web
  service. Build command: `pip install -r requirements.txt`. Start
  command: `gunicorn app:app --bind 0.0.0.0:$PORT`. Set the same env vars
  from `.env` in their dashboard (never commit the file itself).
- **Fly.io** — `fly launch` from this folder, set secrets with
  `fly secrets set SMTP_HOST=... SMTP_USER=... SMTP_PASS=...` etc.
- **PythonAnywhere** — upload the folder, set environment variables in the
  web app config, point it at `app.py`.
- **A small VPS** — `pip install -r requirements.txt`, run with
  `gunicorn app:app --bind 0.0.0.0:4000` under `systemd` or `pm2`, put
  Nginx in front of it for HTTPS.

Whichever you pick, set the same variables from `.env` directly in that
platform's environment/secrets settings — don't upload `.env` itself.

## Notes

- Both endpoints include a honeypot field (`hp_website`) and a basic
  per-IP rate limit (6 requests/minute) to cut down on spam — no extra
  setup needed.
- `waitlist.json` is a flat file for simplicity. For real volume, swap
  `append_to_waitlist()` in `app.py` for a proper database (Postgres,
  SQLite, Airtable, whatever you already use).
- The contact form doesn't currently collect the sender's own email
  address, so replies go out as a fresh email rather than a one-click
  "Reply". Add an email field to the form and a `Reply-To` header in
  `send_email()` if you want that.
