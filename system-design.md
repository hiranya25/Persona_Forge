# Persona Forge — System Design

> Status: **In progress** — written section by section, each one reviewed and
> approved before it lands here. Sections marked _TBD_ are not designed yet.

## Contents

1. [Overview & goals](#1-overview--goals)
2. [Users, roles & portals](#2-users-roles--portals)
3. [Features per portal](#3-features-per-portal)
4. High-level architecture — _TBD_
5. AI/ML pipeline — _TBD_
6. Data model — _TBD_
7. API design — _TBD_
8. Multi-tenancy & security — _TBD_
9. Model training & evaluation — _TBD_
10. Deployment, monitoring & CI — _TBD_
11. Phased roadmap — _TBD_

[Appendix A — Decision log](#appendix-a--decision-log)

---

## 1. Overview & goals

Persona Forge is a **multi-tenant platform** where companies use AI assistants
that:

- answer **only from approved documents**, citing their sources;
- follow a **versioned rule set** (a *persona*): tone, scope, forbidden topics,
  and escalation rules;
- have **every answer checked before delivery** by models trained for that job
  (a gatekeeper on the question, a fact checker on the answer);
- record **every answer in an audit log**, linked to the persona version, model
  versions, sources, and check results that produced it.

The demo domain is **financial filings** (public SEC 10-K / 10-Q reports),
because the data is free, realistic, and number-heavy, which makes
hallucinations easy to detect and measure.

### Goals

- **Grounded answers** — every factual claim traceable to a source passage.
- **Hard rule enforcement** — out-of-scope, forbidden, and jailbreak requests
  are refused, not just discouraged.
- **Full traceability** — any answer can be reconstructed from the audit log.
- **Human in the loop** — uncertain answers go to a reviewer; their labels
  improve the models over time.
- **Free to run** — CPU-only inference, models trained on free notebook GPUs,
  no paid APIs.

### Non-goals

- A general-purpose chatbot.
- Training a large language model from scratch (we fine-tune open-weight ones).
- Real billing or payments.
- Investment advice of any kind.

---

## 2. Users, roles & portals

The platform has **two portals** and **five roles**.

| Portal | Role | Who | Can see data of |
|---|---|---|---|
| **Admin portal** | **Platform Admin** | The platform operator | All companies — metadata and metrics, not private conversations by default |
| **Company portal** | **Company Admin** | The company's manager / IT owner | Own company only |
| | **Analyst** | Everyday user | Own conversations + the company's documents |
| | **Reviewer** | Compliance / QA person | The company's review queue + audit log |
| | **Viewer / Auditor** | Internal or external auditor | Read-only audit log + reports |

- A user belongs to **exactly one company** (Platform Admins belong to none).
- A user may hold **several roles** within their company (e.g. Company Admin +
  Reviewer).
- Companies join **by invitation only** — see [Onboarding](#onboarding).

### Onboarding

1. Platform Admin creates the company and sets its limits.
2. Platform Admin invites the company's first **Company Admin** by email link.
3. The Company Admin accepts, sets a password, and invites the rest of their
   team with roles.

There is no public sign-up.

---

## 3. Features per portal

### 3.1 Admin portal (Platform Admin)

| Area | Features |
|---|---|
| **Companies** | Create, suspend, delete; set limits (max users, documents, queries/day); invite the first Company Admin |
| **Persona templates** | Create, version, and publish templates (e.g. *Financial Filings Analyst*) that companies clone |
| **Shared document library** | Add public documents (SEC filings), track processing status, re-index |
| **Model registry** | List every model version (gatekeeper, fact checker, embedder, writer); promote or roll back |
| **Evaluation dashboard** | Run the evaluation suite; compare metrics across model versions |
| **Training data** | Browse review labels from companies that **opted in** to sharing; export datasets for retraining |
| **System monitoring** | Latency, errors, decision mix (pass / regenerate / refuse / escalate), usage per company |
| **Platform audit log** | Record of every admin action |

### 3.2 Company portal

**Company Admin**

- **Users** — invite, assign roles, deactivate.
- **Personas** — clone a platform template, edit, version, activate, roll back.
  A company can have **several active personas**; analysts pick one per
  conversation.
- **Private documents** — upload, see processing status, delete. Visible only
  to this company.
- **Settings** — verifier strictness thresholds; which shared-library
  collections are enabled; **opt in / out of sharing review labels** for model
  retraining.
- **Usage dashboard** — queries, decision mix, limits consumed.

**Analyst**

- Chat with any active persona of their company.
- Every answer shows its **sources** (document, page, passage).
- Conversation history.
- 👍 / 👎 feedback on answers.
- Escalated answers show **"Under review"**; when a Reviewer resolves them,
  the final answer appears in the conversation and the analyst is
  **notified**.

**Reviewer**

- **Review queue** of escalated answers — approve, correct, or reject, with
  notes. The decision is delivered back to the analyst's conversation.
- Search, filter, and export the **audit log**.

**Viewer / Auditor**

- Read-only audit log, reports, and exports.

---

## Appendix A — Decision log

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | Who is the Admin side for | Platform owner (SaaS operator) | Matches a real multi-tenant B2B product |
| D2 | Company roles | Company Admin, Analyst, Reviewer, Viewer/Auditor | Separates usage, compliance, and oversight duties |
| D3 | Document sources | Shared public library + private per-company uploads | Demo works out of the box; tenants still get isolation |
| D4 | Persona ownership | Platform templates, cloned and customized by companies | Good defaults with per-company control |
| D5 | Company onboarding | Invite-only | Realistic for B2B; no abuse surface from open sign-up |
| D6 | Review labels for retraining | Opt-in per company | Feeds the training loop while respecting tenant privacy |
| D7 | Escalation experience | "Under review" + notification with the final answer | Analyst always gets a resolution, not a dead end |
