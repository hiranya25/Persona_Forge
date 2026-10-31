# Persona Forge — Product Preview (Mock)

A clickable prototype of the Persona Forge platform — built to feel like
software your buyer already operates. Plain HTML/CSS/JS, no build step, no
backend, no real model. Every number, message, and log entry is
hand-written sample data in `js/mockData.js`, cross-referenced against the
PRD, Roadmap, and Concept & Monetization docs.

## File structure

```
persona-forge-product-mock/
├── index.html          Login gate + the 8-view app shell
├── css/
│   └── app.css           Sidebar + top-bar chrome, same palette as the landing page
├── js/
│   ├── mockData.js        ← two full tenants' worth of sample data, edit freely
│   └── app.js              Routing, dropdowns, chat, tables, drawers, modals
└── README.md
```

## Running it

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

Sign in with anything — the login form is cosmetic.

## Screens

- **Dashboard** — usage stats, conformance rate, recent activity, a
  per-agent usage breakdown, and a usage-allowance alert banner that
  appears automatically once a tenant crosses 85% of its monthly
  allowance (try switching to Ashford Partners — it's at 92%)
- **Chat** — a workspace: conversation list, typing indicator, timestamped
  messages, scripted persona-locked replies with Verified/Flagged badges
- **Persona** — the active spec, an example transcript, a "Validated ✓"
  indicator, version history, and a locked "+ Add persona" button
- **Agents** — the preset agent library, now showing each agent's expected
  output alongside its inputs and connectors
- **Agent Builder** *(sidebar, Phase 2)* — shown but locked; clicking it
  explains what it will do and when
- **Controls & Audit** — review queue, paginated/filterable audit log, and
  a locked "Schedule report" action
- **Users** — table with working Invite, plus a "Manage" action per row
  (change role or remove a user)
- **Billing** — plan, usage against allowance, invoice history, and an
  Add-ons catalog (backend build-out, extra persona pack, premium model
  swap-in, on-prem deployment)
- **Security** — authentication methods (MFA active, SSO/SAML shown
  locked) and a tenant-scoped **admin activity log**, kept separate from
  the conversation-level audit trail

## Two full tenants

Switching tenants in the org switcher (top bar) swaps every screen's data:
Northbridge Capital (buyout fund, Growth plan, deeper history) and Ashford
Partners (growth-equity fund, Starter plan, near its token allowance).

## What's locked, and why

Three places show a feature as visible-but-locked rather than omitting it
outright: **Agent Builder** in the sidebar, **+ Add persona** on the
Persona screen, and **Schedule report** in Controls & Audit — plus
**SSO/SAML** on the Security screen. Each opens a small modal explaining
what it does and that it's part of Phase 2, sourced directly from the
Roadmap and PRD. This mirrors the Roadmap's own philosophy: a long sales
cycle benefits from showing a prospect the growth path live in the
product, not just describing it in a slide.

## Editing the story it tells

Nearly everything worth changing lives in `js/mockData.js`:

- Two shared catalogs at the top: `ADDONS` (Billing screen) and
  `AUTH_METHODS` (Security screen) — not tenant-specific
- Inside `TENANTS`, each tenant (`northbridge`, `ashford`) is a
  self-contained block: `persona` (now with `validated` and
  `exampleTranscript`), `agents` (now with `expectedOutput`),
  `agentUsage`, `adminActivityLog`, `reviewQueue`, `auditLog`, `users`,
  `billing`, `notifications`, `conversations`, `chatScript`

Add a third tenant by copying one of these blocks, giving it a new key,
and adding it to the org switcher dropdown in `index.html`.

Structural changes (sidebar groups, adding a screen, layout) are in
`index.html` and `css/app.css`; behavior (routing, dropdowns, chat
matching, modals, pagination) is in `js/app.js`.

## Relationship to the landing page

Same palette and type as the landing page (IBM Plex Sans/Mono, same hex
values), built as a dense app shell rather than a spacious marketing page.

Palette reference:

| Token | Hex |
|---|---|
| Ground | `#F6F5F1` |
| Ground (alt panel) | `#EFEDE6` |
| Beige | `#EAE0C9` |
| Beige (deep / borders) | `#DCCBA3` |
| Ink | `#14171C` |
| Ink (soft) | `#4B5159` |
| Accent (teal) | `#2A6F5E` |
| Flag / risk (rust) | `#B5502D` |
| Border | `#DEDBD1` |
