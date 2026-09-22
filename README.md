# Persona Forge — Landing Page + Product Preview

Two things that now work together as one flow: a marketing landing page
(this folder) and a clickable product preview (`app/`). A "Log in" button
on the landing page opens a modal; submitting it drops you straight into
the product preview's dashboard, skipping its own login screen.

Plain HTML/CSS/JS throughout. No build step, no framework.

## File structure

```
persona-forge/
├── index.html          Landing page — nav now includes "Log in"
├── css/
│   └── styles.css        Landing page styles + the login modal
├── js/
│   ├── config.js          ← edit YOUR_EMAIL_HERE, and formEndpoint once deployed
│   └── main.js             Landing page behavior, including the login modal
├── server/                Optional backend — sends real email via your SMTP
│   ├── app.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── app/                    The product preview (separate mini-project)
│   ├── index.html
│   ├── css/app.css
│   ├── js/mockData.js
│   ├── js/app.js
│   └── README.md            Full detail on the product preview itself
└── README.md
```

## How the login flow works

1. Clicking **Log in** in the landing page nav opens a modal (any email/password works — there's no real backend behind it).
2. Submitting it sets a flag in the browser's `localStorage` and redirects to `app/index.html`.
3. The product preview checks that flag on load. If it's set, it skips its own login screen and opens straight to the dashboard. If someone opens `app/index.html` directly (no flag set), its own login screen shows as normal — it still works standalone.
4. Signing out inside the product preview clears the flag, so a fresh visit to `app/index.html` will show its login screen again until someone logs in from either place.

This only works because both pieces are served from the **same origin** —
`localStorage` doesn't cross domains. Keep `app/` nested inside this
folder exactly as it is; don't split them across two different hosts.

## Running it locally

```bash
python3 -m http.server 8000
# open http://localhost:8000 — try "Log in" in the nav
```

## Hosting

Upload or deploy this whole `persona-forge/` folder as one static site —
Netlify, Vercel, GitHub Pages, or any static host. `app/` just needs to
stay as a subfolder of the root for the relative links to keep working.
(`server/` is separate and needs its own always-on host if you use it for
real email delivery — see `server/README.md`.)

## Editing

- **Landing page copy/structure** → `index.html`
- **Landing page styles, including the login modal** → `css/styles.css`
- **Login modal behavior, contact email, backend URL** → `js/main.js`, `js/config.js`
- **The product preview itself** (screens, mock data, tenants) → see `app/README.md` — it's a self-contained project with its own detailed docs

Palette reference (shared by both the landing page and the product preview):

| Token | Hex |
|---|---|
| Ground | `#F6F5F1` |
| Ground (alt section) | `#EFEDE6` |
| Beige | `#EAE0C9` |
| Beige (deep / borders) | `#DCCBA3` |
| Ink | `#14171C` |
| Ink (soft) | `#4B5159` |
| Accent (teal) | `#2A6F5E` |
| Flag / risk (rust) | `#B5502D` |
| Border | `#DEDBD1` |
