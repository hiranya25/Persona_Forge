# Persona Forge — System Design

> Status: **v1 — approved.** Every section was reviewed and approved
> individually; the reasoning behind each choice is in the
> [decision log](#appendix-a--decision-log). Changes from here on are made by
> adding a new decision to the log and updating the affected section.

## Contents

1. [Overview & goals](#1-overview--goals)
2. [Users, roles & portals](#2-users-roles--portals)
3. [Features per portal](#3-features-per-portal)
4. [High-level architecture](#4-high-level-architecture)
5. [AI/ML pipeline](#5-aiml-pipeline)
6. [Data model](#6-data-model)
7. [API design](#7-api-design)
8. [Multi-tenancy & security](#8-multi-tenancy--security)
9. [Model training & evaluation](#9-model-training--evaluation)
10. [Deployment, monitoring & CI](#10-deployment-monitoring--ci)
11. [Phased roadmap](#11-phased-roadmap)

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
3. The Company Admin accepts, sets a password, and sets up their second
   factor.
4. The Company Admin creates accounts for the rest of the team: email, roles,
   and an **initial password**.

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

- **Users** — create accounts (email, roles, initial password), reset passwords, change roles, deactivate.
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

## 4. High-level architecture

```
 ┌──────────────┐   ┌────────────────┐
 │ Admin portal │   │ Company portal │      React + TypeScript (one codebase)
 └──────┬───────┘   └───────┬────────┘
        └──── HTTPS / JSON + Server-Sent Events ────┐
                            ▼                       │
                ┌───────────────────────┐           │
                │   API service         │  FastAPI: auth, roles, tenants,
                │   (modular monolith)  │  personas, chat, review, audit
                └───┬──────────┬────────┘
                    │          │ jobs
        ┌───────────▼──┐   ┌───▼────────────────┐
        │ Inference    │   │ Background worker  │  document ingestion, eval runs,
        │ service      │   │                    │  notifications, label exports
        │ guard, fact  │   └───┬────────────────┘
        │ checker,     │       │
        │ embedder,    │       │
        │ reranker     │       │
        │ (ONNX, CPU)  │       │
        └──────┬───────┘       │
               │      ┌────────▼─────────┐   ┌────────────┐   ┌──────────────┐
               │      │ Postgres         │   │ Redis      │   │ File storage │
               │      │ app data +       │   │ job queue, │   │ uploaded     │
               │      │ pgvector +       │   │ rate limit,│   │ documents    │
               │      │ full-text search │   │ pub/sub    │   │ (volume)     │
               │      └──────────────────┘   └────────────┘   └──────────────┘
        ┌──────▼───────┐
        │ Ollama       │  writer LLM (GGUF, CPU)
        └──────────────┘
```

### 4.1 Components

| Component | Responsibility | Technology |
|---|---|---|
| **Web app** | Both portals. One codebase with two route trees — `/admin/*` (Platform Admin) and `/app/*` (company roles) — sharing a component library and the existing palette | React, TypeScript, Vite |
| **API service** | The only public backend. Authentication, role checks, tenant isolation, business logic, orchestration of the AI pipeline, audit writes | FastAPI (Python), SQLAlchemy, Pydantic |
| **Inference service** | Internal-only. Keeps the small models loaded in memory and serves them over HTTP: gatekeeper, embedder, reranker, fact checker | FastAPI + ONNX Runtime (CPU, INT8) |
| **Writer LLM** | Generates answers from retrieved passages under the persona's rules | Ollama serving a fine-tuned GGUF model |
| **Background worker** | Slow or deferred work: parse → chunk → embed documents, run evaluation suites, send notifications, export training labels | Python worker on a Redis queue |
| **Postgres** | System of record: tenants, users, personas, conversations, audit log, document chunks, **vectors (pgvector)**, and **keyword search (full-text)** — so hybrid search is one query with a tenant filter | PostgreSQL 16 + pgvector |
| **Redis** | Job queue, rate limiting, pub/sub for live progress and notifications | Redis |
| **File storage** | Original uploaded documents | Local Docker volume (S3-compatible MinIO is a drop-in later) |

The API service is a **modular monolith**: one deployable, internally split
into modules with clear boundaries — `auth`, `tenants`, `users`, `personas`,
`documents`, `chat`, `review`, `audit`, `models`, `evals`. Any module can be
split into its own service later without changing the others' contracts.

### 4.2 How a chat message flows

1. The analyst sends a question; the API authenticates them, checks their role
   and their company's limits, and opens a **Server-Sent Events** stream.
2. The API runs the AI pipeline (detailed in section 5), pushing a **progress
   event** at each stage:
   `Checking question → Searching documents → Writing → Verifying`.
3. The answer is shown **only after verification** — never word-by-word —
   so unverified text never reaches the user.
4. The final decision (pass / refuse / escalate) and everything that produced
   it is written to the audit log **in the same transaction** as the message.
5. Escalated answers land in the company's review queue; when a Reviewer
   resolves one, the worker pushes a notification and the final answer into the
   analyst's conversation.

### 4.3 Why this shape

- **One language (Python)** across API, ML, and training code.
- **Modular monolith** — far simpler to build and run than microservices, with
  boundaries clean enough to split later.
- **Separate inference service** — models load once and stay in memory; they
  can be upgraded or rolled back without redeploying the API.
- **One database** — pgvector + Postgres full-text keep app data, vectors, and
  keyword index together, so tenant filtering and transactions are trivial.
- **Entirely free and local** — every component runs on a laptop CPU via
  `docker compose up`.

---

## 5. AI/ML pipeline

Every question goes through the same stages. The API service orchestrates
them; the small models run in the inference service and the writer runs in
Ollama.

```
question ─► [0 Rewrite] ─► [1 Input guard] ─► [2 Retrieve] ─► [2b Evidence?] ─► [3 Write] ─► [4 Verify] ─► [5 Decide] ─► [6 Record]
                               │ violation          │ nothing relevant                 ▲            │
                               ▼                    ▼                                  │  1 retry   │
                            REFUSE          "not in the documents"                     └────────────┘
```

### 5.1 Stages

**0. Rewrite follow-ups** — only when the conversation has history. The writer
LLM rewrites the latest message into a standalone question (*"and in 2022?"* →
*"What was Apple's total revenue in fiscal 2022?"*). The standalone question is
used by every later stage and stored in the audit log.

**1. Input guard** — two trained models, run before any expensive work:

- **Attack detector** — classifies the question as `benign`, `jailbreak`, or
  `prompt_injection`.
- **Rule matcher** — a cross-encoder that scores a *(text, rule)* pair:
  *"does this text violate this rule?"* It runs once per forbidden-topic rule
  in the active persona, plus once against the persona's **scope** statement
  (*"is this question in scope?"*). Because it learns the general skill of
  matching text against a rule written in plain English, it works on
  **custom rules a company writes that the model has never seen**.

A clear violation → **REFUSE** with the persona's refusal message, without
calling the writer. A borderline score is recorded and carried forward to the
decision stage.

**2. Retrieve** — hybrid search, always filtered to the company's private
documents plus the shared collections it has enabled:

1. Keyword search (Postgres full-text) → top 30 passages.
2. Vector search (pgvector, fine-tuned embedder) → top 30 passages.
3. Merge with **Reciprocal Rank Fusion**.
4. **Reranker** (cross-encoder) scores the merged set → keep the top 5.

**2b. Evidence check** — if the best reranker score is below the evidence
threshold, reply *"I couldn't find this in the available documents"* without
calling the writer. This is the cheapest and most reliable hallucination
defence.

**3. Write** — the writer LLM gets a prompt built from:

- the persona: tone, scope, forbidden topics, escalation rule;
- fixed instructions: answer **only** from the sources, cite a source label
  (`[S1]`…`[S5]`) on **every** sentence, say so plainly when the sources don't
  contain the answer;
- the 5 passages, labelled `S1`…`S5`;
- on a retry, the specific failures from stage 4 (e.g. *"sentence 2 cites a
  figure not in S3"*).

Low temperature (≈0.1) for consistent, factual output.

**4. Verify** — four independent checks on the draft answer:

| Check | Question it answers | How |
|---|---|---|
| **a. Citations** | Does every sentence cite a source that was actually provided? | Deterministic parsing |
| **b. Numbers** | Does every number in the answer appear in the source it cites? | Deterministic: normalise units, scales, currencies, percentages, and years (`$383.3B` ≡ `383,285 million`) with a rounding tolerance |
| **c. Fact checker** | Is each part of the answer supported by the cited passages? | **Trained model** — token-level hallucination detector over *(passages, answer)*; token scores are aggregated per sentence |
| **d. Output guard** | Did the answer break a persona rule anyway? | The **rule matcher** again, run on the answer against the forbidden-topic rules |

**5. Decide**

| Outcome | When | Analyst sees |
|---|---|---|
| **PASS** | All checks pass with confidence | The answer with its sources |
| **REGENERATE** | A check fails on the **first** attempt | Nothing yet — the writer retries once with the failures as feedback |
| **REFUSE** | Input guard or output guard finds a clear violation | The persona's refusal message |
| **ESCALATE** | Checks still fail after the retry, **or** any score is borderline | *"Under review"* — the case goes to the review queue (section 3.2) |

"Clear" and "borderline" are defined by **thresholds** taken from the
company's **strictness** setting — three presets (*Lenient*, *Standard*,
*Strict*), each a set of thresholds calibrated on the evaluation set
(section 9). Borderline cases go to a human, not to an LLM judge; the
**LLM-as-judge is used only offline**, in evaluations, to keep live latency low.

**6. Record** — one audit entry per answer, written in the same transaction as
the message: original and standalone question, persona version, every model
version, retrieved passage IDs with scores, draft answer(s), every check result
and score, the decision, and timings for each stage.

### 5.2 Models

| ID | Model | Task | Base model (CPU-friendly) | Trained by us? | Served as |
|---|---|---|---|---|---|
| **M1** | Attack detector | Text → benign / jailbreak / prompt injection | ModernBERT-base or DeBERTa-v3-small | **Yes** — fine-tuned | ONNX INT8 |
| **M2** | Rule matcher | *(text, rule)* → violation probability | ModernBERT-base / DeBERTa-v3-base cross-encoder | **Yes** — fine-tuned | ONNX INT8 |
| **M3** | Embedder | Text → 384-dim vector | bge-small-en-v1.5 | **Yes** — contrastive fine-tune on finance Q&A | ONNX INT8 |
| **M4** | Reranker | *(question, passage)* → relevance | bge-reranker-base | Pretrained first; fine-tune is a stretch goal | ONNX INT8 |
| **M5** | Fact checker | *(passages, answer)* → per-token "unsupported" probability | ModernBERT-base (long context) | **Yes** — fine-tuned | ONNX INT8 |
| **M6** | Writer | Persona prompt + passages → cited answer | Small open-weight instruct LLM — 3B–4B by default (16 GB RAM), 1.5B as a configurable fallback | **Yes** — QLoRA SFT, then DPO | GGUF Q4 via Ollama |

Every model has a **version** in the model registry (section 3.1); the active
version of each is recorded with every answer.

### 5.3 Security inside the pipeline

- **Indirect prompt injection** — uploaded documents can contain hidden
  instructions. The attack detector (M1) also scans every passage **at
  ingestion time**; flagged passages are quarantined and shown to the Company
  Admin instead of being indexed.
- **Fail closed** — if the inference service or the writer is unavailable, the
  analyst gets an error, **never** an unverified answer.
- **Tenant filter at the query level** — retrieval always filters by company,
  so one company's passages can never reach another company's prompt.

### 5.4 Latency budget (laptop CPU, estimated)

| Stage | Typical |
|---|---|
| Rewrite (only with history) | 1–2 s |
| Input guard (M1 + M2 × rules) | 50–150 ms |
| Retrieve + rerank | 150–400 ms |
| Write (≈150 tokens) | 4–10 s |
| Verify (checks a–d) | 200–500 ms |
| **Total, first attempt** | **≈ 5–12 s** |
| Worst case (one retry) | ≈ 10–22 s |

The writer dominates, which is why it gets a live progress display (section
4.2) and why borderline cases go to humans rather than to more LLM calls.

---

## 6. Data model

All data lives in one Postgres database. Conventions:

- Primary keys are UUIDs (except `audit_log`, which uses a sequence).
- **Every tenant-scoped table carries `company_id`**, and every query filters on
  it (enforcement is described in section 8). Where `company_id` is `NULL`, the
  row belongs to the platform (shared library, templates, Platform Admins).
- Anything that explains a past answer — persona versions, answer runs, audit
  entries — is **immutable**: new versions are inserted, old rows are never
  updated.

### 6.1 Entity overview

```
companies ─┬─< users ─< user_roles
           ├─< invitations
           ├─< personas ─< persona_versions >─ persona_template_versions >─ persona_templates
           ├─< collections (private) ─< documents ─< chunks      (collections with company_id NULL = shared library)
           ├─< company_collections >─ collections (shared)
           ├─< conversations ─< messages ─── answer_runs ─< run_attempts
           │                                      ├─< run_retrievals >─ chunks
           │                                      └── review_items
           ├─< labels
           └─< audit_log (one hash chain per company; company_id NULL = platform chain)

model_versions · eval_runs · notifications · usage_daily
```

### 6.2 Tables

**Tenancy & identity**

| Table | Key columns |
|---|---|
| `companies` | `id`, `name`, `slug`, `status` (active / suspended), `limits` (max users, max documents, queries per day), `strictness` (lenient / standard / strict), `share_labels` (bool, opt-in), `created_at` |
| `users` | `id`, `company_id` (NULL for Platform Admins), `email` (unique), `password_hash` (Argon2id), `full_name`, `is_platform_admin`, `status` (invited / active / deactivated), `last_login_at` |
| `user_roles` | `user_id`, `role` (company_admin / analyst / reviewer / viewer) — one row per role held |
| `invitations` | `id`, `company_id`, `email`, `roles`, `token_hash`, `expires_at`, `accepted_at`, `invited_by` |
| `refresh_tokens` | `id`, `user_id`, `family_id`, `token_hash`, `expires_at`, `revoked_at` — rotated on every use; reuse of an old token revokes the whole family |
| `mfa_methods` | `id`, `user_id`, `type` (passkey / totp / email_otp), `label`, `credential` (WebAuthn public key + sign counter, or encrypted TOTP secret), `created_at`, `last_used_at` |
| `otp_codes` | `id`, `user_id`, `purpose` (login / mfa), `code_hash`, `expires_at`, `attempts`, `used_at` |
| `recovery_codes` | `id`, `user_id`, `code_hash`, `used_at` — admins only |

**Personas**

| Table | Key columns |
|---|---|
| `persona_templates` | `id`, `name`, `description`, `status` (draft / published / archived) |
| `persona_template_versions` | `id`, `template_id`, `version`, `spec`, `published_at` — immutable |
| `personas` | `id`, `company_id`, `name`, `cloned_from` (template version), `status` (active / inactive), `current_version_id` |
| `persona_versions` | `id`, `persona_id`, `company_id`, `version`, `spec`, `change_note`, `created_by`, `created_at` — immutable |

The `spec` is JSON validated against a schema:

```json
{
  "tone": "Neutral, precise, always cites sources.",
  "scope": "Questions about the financial filings in this workspace.",
  "forbidden_topics": [
    { "id": "r1", "text": "Investment recommendations or buy/sell opinions" },
    { "id": "r2", "text": "Predictions of future stock prices" }
  ],
  "escalation": "If unsure, say so and flag for human review.",
  "refusal_message": "I can't help with that. I can answer questions about the filings themselves.",
  "example_transcripts": [ { "user": "…", "assistant": "…" } ]
}
```

Rule `id`s are stable across versions, so audit entries and labels can point
at the exact rule that fired.

**Documents & search**

| Table | Key columns |
|---|---|
| `collections` | `id`, `company_id` (NULL = shared library), `name`, `description` |
| `company_collections` | `company_id`, `collection_id` — shared collections a company has enabled |
| `documents` | `id`, `company_id`, `collection_id`, `title`, `format` (pdf / html / docx / txt / md), `file_path`, `sha256`, `status` (uploaded / processing / indexed / failed / quarantined), `metadata` (e.g. ticker, fiscal year, form type), `uploaded_by` |
| `chunks` | `id`, `document_id`, `company_id`, `ordinal`, `text`, `page`, `section`, `token_count`, `embedding` (`vector(384)`), `tsv` (`tsvector`), `embedder_version`, `injection_flag` |

Indexes on `chunks`: **HNSW** on `embedding`, **GIN** on `tsv`, B-tree on
`company_id` and `document_id`. A new embedder version re-embeds chunks in the
background; search uses only chunks matching the active `embedder_version`.

**Chat & pipeline trace**

| Table | Key columns |
|---|---|
| `conversations` | `id`, `company_id`, `user_id`, `persona_id`, `title`, `created_at` |
| `messages` | `id`, `conversation_id`, `company_id`, `role` (user / assistant), `content`, `status` (final / under_review / resolved), `answer_run_id`, `created_at` |
| `answer_runs` | `id`, `company_id`, `message_id`, `persona_version_id`, `standalone_question`, `decision` (pass / refuse / escalate / no_evidence), `attempts`, `model_versions`, `stage_timings_ms`, `created_at` — one row per answered question |
| `run_attempts` | `id`, `run_id`, `attempt_no`, `draft_answer`, `check_results` (citations, numbers, fact checker spans and scores, output guard), `prompt_hash` |
| `run_retrievals` | `run_id`, `chunk_id`, `rank`, `keyword_score`, `vector_score`, `rerank_score`, `in_prompt` (S1…S5 label or NULL) |
| `feedback` | `id`, `message_id`, `user_id`, `rating` (+1 / −1), `comment` |

**Review & training labels**

| Table | Key columns |
|---|---|
| `review_items` | `id`, `company_id`, `run_id`, `reason`, `status` (open / approved / corrected / rejected), `assigned_to`, `resolved_by`, `resolved_at`, `corrected_answer`, `notes` |
| `labels` | `id`, `company_id`, `run_id`, `source` (review / feedback), `target_model` (M1 / M2 / M5 / M6), `payload`, `shareable`, `created_at` |

`shareable` is copied from the company's `share_labels` setting **at the
moment the label is created**, so turning sharing off later never
retroactively exposes or hides past labels by accident. Only `shareable`
labels appear in the Platform Admin's training-data view.

**Audit log** — see 6.3.

**Platform**

| Table | Key columns |
|---|---|
| `model_versions` | `id`, `model_key` (M1–M6), `version`, `artifact_uri`, `metrics`, `status` (candidate / active / retired), `promoted_by`, `promoted_at` |
| `eval_runs` | `id`, `model_versions`, `dataset_version`, `status`, `metrics`, `started_by`, `started_at`, `finished_at` |
| `notifications` | `id`, `user_id`, `company_id`, `type`, `payload`, `read_at` |
| `access_grants` | `id`, `company_id`, `admin_user_id`, `reason`, `scope`, `expires_at`, `revoked_at`, `created_at` — break-glass access (section 8.4) |
| `usage_daily` | `company_id`, `date`, `queries`, `decisions` — counters used to enforce limits and draw usage charts |

### 6.3 Hash-chained audit log

```
audit_log: id (sequence) · company_id · actor_user_id · actor_type (user / system)
           · action · entity_type · entity_id · payload · created_at
           · prev_hash · hash
```

- **One chain per company**, plus one platform chain (`company_id` NULL), so a
  company can export and verify its own chain independently.
- `hash = SHA-256(prev_hash ‖ canonical JSON of the entry)`. The first entry of
  a chain uses a fixed genesis value as `prev_hash`.
- Appends take a per-chain lock so concurrent writes can't fork the chain.
- The database role used by the API has **INSERT and SELECT only** on
  `audit_log` — no UPDATE or DELETE.
- **"Verify integrity"** (Platform Admin, Company Admin, Viewer) recomputes the
  chain and reports the first broken link, if any. Any edit or deletion breaks
  every hash after it.

**What is audited:** every answer run (with a hash of its full trace), review
decisions, persona changes, user and role changes, invitations, document
uploads and deletions, settings changes, logins, model promotions and
rollbacks, and every Platform Admin action.

### 6.4 Document ingestion

Supported formats: **PDF** (text-based; scanned images are out of scope),
**HTML** (SEC EDGAR filings), **Word (.docx)**, **plain text / Markdown**.

`uploaded → processing → indexed` (or `failed` / `quarantined`), run by the
background worker:

1. **Store** the original file; record its SHA-256 (duplicates are rejected
   per company).
2. **Extract** text with structure — page numbers (PDF), headings and tables
   (HTML, DOCX).
3. **Chunk** into ~300–500-token passages along section boundaries, with a
   small overlap; tables are kept whole where possible.
4. **Scan** each chunk with the attack detector (M1); flagged chunks are
   quarantined for Company Admin review (section 5.3).
5. **Embed** (M3) and build the full-text vector, then mark the document
   `indexed`.

---

## 7. API design

### 7.1 Conventions

- **REST + JSON** under `/api/v1`, documented automatically with OpenAPI
  (FastAPI's `/docs`).
- **Two route trees**, mirroring the two portals:
  - `/api/v1/...` — company portal. The company is **always taken from the
    session, never from the URL or body**, so a user cannot even name another
    company's data.
  - `/api/v1/admin/...` — Platform Admin only.
- **Auth** via httpOnly cookies (section 8.1); state-changing requests also
  send an `X-CSRF-Token` header.
- **Errors** use one shape (RFC 9457 *problem details*):
  `{ "type", "title", "status", "detail", "request_id" }`.
- **Pagination** is cursor-based: `?limit=50&cursor=…` → `{ items, next_cursor }`.
- **Live updates** use Server-Sent Events: one stream per chat answer, one per
  user for notifications.
- **Rate limits** per user and per company (Redis), returning `429` with
  `Retry-After`.

### 7.2 Endpoints — company portal

| Group | Endpoints | Roles |
|---|---|---|
| **Auth** | `POST /auth/login` (email + password), `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/mfa/verify`, `POST /auth/passkey/options`, `POST /auth/passkey/verify`, `POST /auth/recovery`, `POST /auth/refresh`, `POST /auth/logout`, `POST /invitations/{token}/accept` | Public / any |
| **Me** | `GET /me`, `POST /me/password`, `GET/POST/DELETE /me/mfa-methods`, `POST /me/recovery-codes` | Any signed-in user |
| **Users** | `GET /users`, `POST /users` (email, roles, initial password), `PATCH /users/{id}` (roles, status), `POST /users/{id}/reset-password` | Company Admin |
| **Settings & usage** | `GET/PATCH /settings` (strictness, label sharing, enabled collections), `GET /usage` | Company Admin |
| **Personas** | `GET /personas`, `POST /personas` (clone a template), `GET /personas/{id}/versions`, `POST /personas/{id}/versions`, `POST /personas/{id}/activate`, `POST /personas/{id}/rollback` | Company Admin (read: all roles) |
| **Templates** | `GET /persona-templates` | Company Admin |
| **Documents** | `GET /documents`, `POST /documents` (multipart upload), `GET /documents/{id}`, `DELETE /documents/{id}`, `GET /documents/quarantine`, `POST /documents/quarantine/{chunk_id}/release` | Company Admin (read: Analyst) |
| **Collections** | `GET /collections` (private + enabled shared) | Company Admin, Analyst |
| **Chat** | `GET/POST /conversations`, `GET /conversations/{id}`, `POST /conversations/{id}/messages` → SSE stream, `POST /messages/{id}/feedback` | Analyst |
| **Review** | `GET /review-items`, `GET /review-items/{id}` (full trace), `POST /review-items/{id}/resolve` (approve / correct / reject + notes) | Reviewer |
| **Audit** | `GET /audit`, `GET /audit/export`, `POST /audit/verify` | Reviewer, Viewer, Company Admin |
| **Notifications** | `GET /notifications`, `GET /notifications/stream` (SSE), `POST /notifications/{id}/read` | Any signed-in user |

### 7.3 Endpoints — admin portal

| Group | Endpoints |
|---|---|
| **Companies** | `GET/POST /admin/companies`, `PATCH /admin/companies/{id}` (limits, status), `DELETE /admin/companies/{id}`, `POST /admin/companies/{id}/invite-admin` |
| **Persona templates** | `GET/POST /admin/persona-templates`, `POST /admin/persona-templates/{id}/versions`, `POST /admin/persona-templates/{id}/publish` |
| **Shared library** | `GET/POST /admin/collections`, `POST /admin/collections/{id}/documents`, `POST /admin/collections/{id}/reindex` |
| **Models** | `GET /admin/models`, `POST /admin/models/{id}/promote`, `POST /admin/models/{id}/rollback` |
| **Evaluations** | `GET/POST /admin/eval-runs`, `GET /admin/eval-runs/{id}`, `GET /admin/eval-runs/compare?a=…&b=…` |
| **Training data** | `GET /admin/labels` (shareable only), `POST /admin/labels/export` |
| **Monitoring** | `GET /admin/metrics` (latency, errors, decision mix, usage per company) |
| **Break-glass** | `POST /admin/access-grants`, `GET /admin/access-grants`, `POST /admin/access-grants/{id}/revoke` |
| **Platform audit** | `GET /admin/audit`, `POST /admin/audit/verify` |

### 7.4 Chat stream example

`POST /api/v1/conversations/{id}/messages` with `{ "content": "And in 2022?" }`
returns `text/event-stream`:

```
event: stage    data: {"stage": "rewriting"}
event: stage    data: {"stage": "checking_question"}
event: stage    data: {"stage": "searching", "passages_found": 5}
event: stage    data: {"stage": "writing", "attempt": 1}
event: stage    data: {"stage": "verifying"}
event: result   data: {"message_id": "…", "decision": "pass",
                       "answer": "Apple's total net sales in fiscal 2022 were $394.3 billion [S1].",
                       "sources": [{"label": "S1", "document": "Apple 10-K 2022", "page": 21, "excerpt": "…"}]}
```

Other `result` decisions: `refuse` (with the persona's message), `no_evidence`,
and `escalated` (the message shows *"Under review"*; the final answer arrives
later through the notifications stream).

### 7.5 Inference service (internal)

Reachable only on the internal Docker network and protected with a shared
service token. Every response includes the model version that produced it.

| Endpoint | Input → output |
|---|---|
| `POST /v1/attack` | texts → `benign / jailbreak / prompt_injection` + probabilities (M1) |
| `POST /v1/rules` | (text, [rules]) → violation probability per rule (M2) |
| `POST /v1/embed` | texts → 384-dim vectors (M3) |
| `POST /v1/rerank` | (question, passages) → relevance scores (M4) |
| `POST /v1/factcheck` | (passages, answer) → per-token and per-sentence unsupported scores (M5) |
| `GET /v1/health` | loaded models and versions |

The writer (M6) is called through Ollama's own HTTP API.

---

## 8. Multi-tenancy & security

### 8.1 Authentication

| Users | First factor | Second factor | Recovery |
|---|---|---|---|
| **Platform Admin, Company Admin** | Password (Argon2id) | **Mandatory** — one of: **passkey** (WebAuthn), **authenticator app** (TOTP), or **email OTP** | 10 one-time **recovery codes**, shown once, stored hashed |
| **Analyst, Reviewer, Viewer** | **Either** email + password **or** email OTP — the user chooses at each sign-in | — | Email OTP, or a password reset by their Company Admin |

- **Employee accounts:** the Company Admin creates each account with an
  initial password. Users can then sign in with their password or with an
  email code, and can change their password at any time.
- **Email OTP:** 6 digits, valid 10 minutes, single use, stored hashed, at most
  5 attempts per code, and rate-limited per email and per IP. Responses are the
  same whether or not the email exists.
- An admin can register **several second factors** (e.g. a passkey plus an
  authenticator app). Using a recovery code forces registering a new method.
- **Sessions:** a 15-minute access token and a 7-day refresh token, both in
  `httpOnly`, `Secure`, `SameSite=Lax` cookies. Refresh tokens rotate on every
  use; reusing an old one revokes the whole session family (theft detection).
  CSRF protection uses a double-submit token.
- **Email delivery:** **Mailpit** in development (a free local inbox that
  catches every email), any SMTP account in production.
- Logins, failed logins, MFA changes, and recovery-code use are all audited.

### 8.2 Authorization (role-based access)

Permissions are checked in the API on **every endpoint**, never just hidden in
the UI.

| Capability | Platform Admin | Company Admin | Analyst | Reviewer | Viewer |
|---|:-:|:-:|:-:|:-:|:-:|
| Manage companies, templates, shared library, models, evals | ✅ | — | — | — | — |
| Manage company users, settings, personas, documents | — | ✅ | — | — | — |
| Chat with personas | — | — | ✅ | — | — |
| Read documents & personas | — | ✅ | ✅ | ✅ | ✅ |
| Work the review queue | — | — | — | ✅ | — |
| Read / export / verify the audit log | Platform chain | ✅ | — | ✅ | ✅ |
| See company usage metrics | ✅ (all) | ✅ | — | — | — |
| Read company conversations | Break-glass only | — | Own only | Escalated only | — |

A user with several roles gets the union of their permissions.

### 8.3 Tenant isolation — two layers

1. **Application layer:** the company comes from the session. Every repository
   query is built through a tenant-scoped session that adds
   `WHERE company_id = :current_company` automatically.
2. **Database layer:** Postgres **Row-Level Security** on every tenant-scoped
   table. Each request sets `app.company_id` for its transaction; policies
   reject any row from another company **even if the application layer has a
   bug**.

Shared-library rows (`company_id` NULL) are readable by a company only when it
has enabled that collection. An automated **cross-tenant test suite** tries to
reach another company's data through every endpoint and must always fail.

### 8.4 Break-glass access

1. The Platform Admin requests access to one company with a **written reason**
   and a duration (maximum 24 hours).
2. A read-only `access_grant` is created; it **expires automatically** and can
   be revoked at any time.
3. The **Company Admin is notified immediately**, and the grant plus every
   record viewed under it are written to **both** the company's and the
   platform's audit chains.
4. Break-glass access never allows changes — read-only, always.

### 8.5 Data & application security

- **Secrets** only in environment variables (`.env` locally, never committed).
- **Uploads:** size limit, file type checked by content (not by extension),
  parsed in the background worker, never executed (no macros, no scripts).
- **Prompt injection** in documents: scanned at ingestion (section 5.3).
- **Logs** carry request IDs and metrics, **not** question or answer text;
  content lives only in the database, behind tenant isolation.
- **Web security:** strict CORS (the web app's origin only), security headers
  (CSP, HSTS, `X-Frame-Options`), input validation through Pydantic schemas,
  and parameterised SQL only.
- **Supply chain:** pinned dependencies, plus automated dependency and
  container image scanning in CI.

---

## 9. Model training & evaluation

### 9.1 Workflow and tools (all free)

```
build dataset ──► train on Kaggle / Colab GPU ──► track in Weights & Biases
      │                                                  │
      ▼                                                  ▼
publish dataset to HF Hub            export (ONNX INT8 / GGUF) ──► publish model to HF Hub
                                                         │
                                                         ▼
                       register as "candidate" ──► evaluation gate ──► promote to "active"
```

- **Training:** Kaggle Notebooks (≈30 free GPU-hours a week) with Google Colab
  as backup. Training code lives in the repo and runs the same way locally on
  small samples, so notebooks only call it.
- **Experiment tracking:** **Weights & Biases** (free personal tier) — every
  run logs its config, dataset version, metrics, and charts; final dashboards
  are made public.
- **Publishing:** every trained model and every dataset we build is
  **published publicly on Hugging Face Hub** with a model/dataset card
  (training data, method, metrics, limitations). The app downloads the active
  versions at startup.
- **Reproducibility:** fixed seeds, pinned library versions, and dataset
  versions recorded in every run and every `eval_runs` row.

### 9.2 Per-model training plans

**M1 — Attack detector** (text → benign / jailbreak / prompt injection)

- **Data:** `deepset/prompt-injections`, `jackhhao/jailbreak-classification`,
  JailbreakBench; *benign* examples from FinanceBench / FinQA questions and
  XSTest's safe-but-scary prompts; **synthetic indirect injections** hidden
  inside real filing passages.
- **Method:** fine-tune ModernBERT-base / DeBERTa-v3-small, cross-entropy with
  class weights.
- **Key metric:** attack recall at a **≤1% false-positive rate** on benign
  finance questions (blocking real users is costly too).

**M2 — Rule matcher** (*(text, rule)* → violation probability)

- **Data — synthetic, built by us:**
  1. A bank of ~300 diverse forbidden-topic rules across domains (finance,
     legal, HR, health, support).
  2. For each rule, an open-weight LLM running on Kaggle generates
     **violating** questions and answers, and **hard negatives** — same topic,
     but allowed (*"What does the 10-K say about the lawsuit?"* is fine;
     *"Will they lose the lawsuit?"* violates *"no predictions about pending
     litigation"*).
  3. Random negatives from other rules, plus safety datasets (BeaverTails,
     ToxicChat) mapped onto rule texts.
  4. ~500 test pairs **checked by hand**.
- **Method:** cross-encoder fine-tune (ModernBERT-base / DeBERTa-v3-base),
  binary cross-entropy.
- **Key metric:** F1 / AUROC on **held-out rules the model never saw in
  training** — this is what proves it handles a company's custom rules.

**M3 — Embedder** (text → vector)

- **Data:** question → passage pairs from FinQA, TAT-QA, and ConvFinQA, plus
  synthetic questions generated from EDGAR passages; **hard negatives** mined
  with BM25.
- **Method:** contrastive fine-tune of bge-small-en-v1.5 with in-batch
  negatives (MultipleNegativesRankingLoss).
- **Key metric:** Recall@5 / nDCG@10 on **held-out companies**, versus the
  untouched base model.

**M4 — Reranker** — pretrained bge-reranker-base at first; fine-tuning on the
same pairs as M3 is a stretch goal.

**M5 — Fact checker** (*(passages, answer)* → unsupported spans)

- **Data:** **RAGTruth** (human-labelled hallucinated spans in RAG answers),
  plus **synthetic finance perturbations**: take correct answers and change a
  number, year, company, or direction (*increased* → *decreased*), so the
  altered span's label is known exactly.
- **Method:** ModernBERT-base token classification over the concatenated
  passages and answer (long context fits ModernBERT).
- **Key metrics:** span- and sentence-level F1 and AUROC, compared against two
  baselines — an off-the-shelf NLI model and an LLM judge.

**M6 — Writer** (persona prompt + passages → cited answer)

- **Stage 1 — SFT (QLoRA):** training examples (persona, question, passages →
  cited answer *or* correct refusal) produced by a **larger open-weight
  teacher model** run on Kaggle's free GPUs (4-bit). Only examples that **pass
  our own verifiers** (citations, numbers, M5, M2) are kept —
  *self-verified distillation*.
- **Stage 2 — DPO:** sample several answers per prompt from the SFT model; an
  answer that passes verification is *chosen*, one that fails is *rejected*.
  **The verifiers generate the preference data** — no human or paid labeller
  needed.
- **Export:** merge LoRA → GGUF (Q4) → Ollama.
- **Key metrics:** first-attempt pass rate, citation accuracy, faithfulness,
  persona-violation rate, refusal correctness — reported for base model → SFT
  → DPO.

### 9.3 Calibration and thresholds

- Each classifier (M1, M2, M5) is **calibrated** with temperature scaling on a
  validation set; reliability diagrams and Expected Calibration Error are
  logged to W&B.
- The three **strictness presets** (section 5.1) are chosen from
  precision–recall curves on the validation set, e.g. *Strict* = recall on
  violations ≥ 98%, *Standard* = best F1, *Lenient* = false-positive rate ≤ 1%.
- The "borderline" band is the score range where calibrated confidence is
  between the preset's lower and upper thresholds.

### 9.4 Evaluation suites

| Suite | Contents | Measures |
|---|---|---|
| **Component** | Each model's held-out test set | The model's own metrics (above) |
| **Golden end-to-end** | FinanceBench (150 questions) + ~300 curated questions over the shared library, each with an expected answer or an expected refusal | Answer correctness, faithfulness, citation precision, decision accuracy |
| **Red team** | Jailbreaks, forbidden-topic requests, out-of-scope questions, documents with hidden injections | Attack block rate, rule-violation leak rate |
| **Over-refusal** | Safe questions that *sound* risky (XSTest-style, finance-flavoured) | False refusal rate |
| **Performance** | Fixed load script | p50 / p95 latency per stage, throughput |

- **Answer correctness** uses exact numeric matching where possible and an
  **offline LLM-as-judge** (the largest open model that fits a free Kaggle
  GPU) otherwise; the judge itself is spot-checked against ~100 human labels.
- Splits are made **by company, by rule, and by document** so no test item
  leaks into training. Eval sets are never used for training.

### 9.5 Release gate

A new model version starts as a **candidate**. It can be promoted to
**active** (from the admin portal) only if the end-to-end and red-team suites
show **no key metric regressing beyond a set tolerance** against the current
active version. Promotion and rollback are one click, versioned, and audited.

### 9.6 Continuous improvement loop

1. Reviewer decisions and 👍/👎 feedback create labels (section 6.2).
2. Labels from companies that **opted in** are exported from the admin portal.
3. They are merged into the training sets as a new dataset version, with
   hard-to-classify examples prioritised (*active learning*).
4. Retraining produces a new candidate, which goes through the release gate.

---

## 10. Deployment, monitoring & CI

### 10.1 Repository layout (monorepo)

```
persona-forge/
├── apps/
│   └── web/                 React + TypeScript — /admin and /app portals
├── services/
│   ├── api/                 FastAPI modular monolith + Alembic migrations
│   ├── inference/           FastAPI + ONNX Runtime — M1–M5
│   └── worker/              Background jobs (ingestion, evals, notifications)
├── ml/
│   ├── data/                Dataset builders (download, synthesise, split)
│   ├── training/            Training scripts per model (run locally or from notebooks)
│   ├── export/              ONNX / GGUF export and quantisation
│   ├── evals/               Evaluation suites and the release-gate script
│   └── notebooks/           Thin Kaggle / Colab launchers that call ml/
├── packages/
│   └── shared/              Shared Python code: persona schema, pipeline types
├── infra/
│   ├── docker/              Dockerfiles, docker-compose (dev and prod profiles)
│   ├── caddy/               Reverse proxy config (HTTPS)
│   └── grafana/             Dashboards and alert rules as code
├── docs/                    Design docs, ADRs, model cards
└── .github/workflows/       CI/CD
```

### 10.2 Environments

| Environment | Where | Details |
|---|---|---|
| **Local development** | Your laptop | `docker compose up` — all services, hot reload, **Mailpit** for emails, seed script with demo companies, users, personas, and filings |
| **Public demo** | **Oracle Cloud Always Free** ARM VM (up to 4 cores / 24 GB RAM) | Same compose file, `prod` profile; **Caddy** in front for automatic HTTPS on a free domain (e.g. DuckDNS); demo accounts for each role, demo data reset nightly |

- Every image is built **multi-arch** (`amd64` + `arm64`), because the free
  Oracle VM is ARM; Ollama and ONNX Runtime both support ARM.
- Configuration follows the twelve-factor style: everything comes from
  environment variables; secrets never enter images or Git.
- **Database migrations** with Alembic run automatically on deploy.
- **Backups:** nightly `pg_dump`, kept on the VM and copied to Oracle's
  always-free object storage.

### 10.3 CI/CD (GitHub Actions — free for public repos)

**On every pull request**

| Step | Tools |
|---|---|
| Lint & format | ruff, ESLint, Prettier |
| Type checks | mypy, `tsc` |
| Unit tests | pytest, Vitest |
| API integration tests against a real Postgres + pgvector service container | pytest |
| **Cross-tenant isolation suite** (section 8.3) | pytest |
| Migration check (upgrade + downgrade on an empty DB) | Alembic |
| **ML smoke eval** — verifier models on a ~50-item subset, CPU only | `ml/evals` |
| Security scans | pip-audit, npm audit, Trivy (images) |
| Build web app and Docker images | Vite, Docker Buildx |

**On merge to `main`:** build multi-arch images → push to GitHub Container
Registry (free) → deploy to the Oracle VM over SSH after a **manual approval**
step → run a post-deploy health check.

**On demand:** the full end-to-end and red-team suites run on the VM (or on
Kaggle for GPU-heavy judging), and results land in the admin portal's
evaluation dashboard (section 3.1).

### 10.4 Monitoring

| What | How |
|---|---|
| **Service metrics** — request rate, errors, p50/p95 latency per pipeline stage, queue depth | Prometheus scraping `/metrics` on the API, inference service, and worker |
| **Dashboards** | Grafana, with dashboards kept as code in `infra/grafana/` |
| **Logs** | Structured JSON with request IDs (no question or answer text — section 8.5) |
| **Alerts** | Grafana alerting by email — service down, error rate, latency, failed backups |
| **ML monitoring** | Daily distributions of M1, M2, and M5 scores; decision mix (refuse / escalate / no-evidence rates) per company; alerts when they drift from the baseline, a signal that a model or the incoming questions have changed |

---

## 11. Phased roadmap

About **12 weeks part-time**. Every phase ends with something that runs end
to end.

| Phase | Duration | Build | Done when |
|---|---|---|---|
| **P0 — Foundations** | 1 week | Monorepo, Docker Compose, CI skeleton, DB schema and migrations, auth (password, email OTP, TOTP, recovery codes), companies, users and roles, Row-Level Security, hash-chained audit log | A Platform Admin can create a company; its admin can sign in with MFA and create users; the cross-tenant test suite passes |
| **P1 — Documents & baseline RAG** | 2 weeks | Ingestion for all four formats, shared library of SEC filings, hybrid search with the **base** embedder, writer via Ollama with a **stock** model, chat over SSE with citations, evaluation harness + golden set v1 | An analyst gets cited answers; **baseline metrics recorded** |
| **P2 — Guardrails v1** | 2 weeks | Persona templates and versioning, input guard and fact checker using **off-the-shelf baselines**, citation and number checks, decision engine with retry, review queue, notifications, core screens of both portals | The full pipeline works end to end with baseline models; red-team and over-refusal suites run |
| **P3 — Train the verifiers** | 3 weeks | Datasets and training for **M1, M2, M3, M5**, calibration, ONNX export, model registry, release gate, publishing to HF Hub | Each trained model beats its baseline; promoted through the gate |
| **P4 — Tune the writer** | 2 weeks | **M6** SFT then DPO, GGUF export | Pass rate up and violation rate down versus the stock model |
| **P5 — Production & launch** | 2 weeks | Passkeys, break-glass access, monitoring and drift alerts, security scans, Oracle deployment, demo accounts, documentation | Public demo live; README with architecture, metrics tables, model links, demo video; write-up published |

**Stretch goals:** fine-tuned reranker (M4), OCR for scanned PDFs, SSO/SAML,
Kubernetes / Helm deployment, a public red-team leaderboard.

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
| D8 | Overall architecture | Modular-monolith FastAPI API + separate inference service + worker + Postgres + Redis + Ollama | Simple to run, clean boundaries, all free and CPU-friendly |
| D9 | Frontend | React + TypeScript, one codebase with `/admin` and `/app` route trees | Job-relevant; shared components across both portals |
| D10 | Vector + keyword search | Postgres + pgvector + full-text search | One store, easy tenant filtering, hybrid search in one query |
| D11 | Waiting experience | Live progress steps via Server-Sent Events; answer shown only after verification | Keeps the "verified before delivery" promise while staying responsive |
| D12 | Custom forbidden-topic rules | Trained rule-matcher cross-encoder on *(text, rule)* pairs + fixed attack detector | Generalises to rules it has never seen; strongest deep-learning component |
| D13 | Follow-up questions | Rewrite into a standalone question using chat history | Natural conversations; cost paid only when there is history |
| D14 | Retries on failed verification | 1 retry with failure feedback, then escalate | Balances answer rate against CPU latency |
| D15 | Borderline scores | Escalate to a human; LLM-as-judge only offline | Keeps live latency low; humans produce training labels |
| D16 | Failure handling | Fail closed — never show an unverified answer | The core promise of the product |
| D17 | Default writer size | 3B–4B model at 4-bit; 1.5B configurable fallback | Fits a 16 GB laptop alongside the rest of the stack |
| D18 | Upload formats | PDF (text-based), HTML, DOCX, TXT/Markdown | Covers SEC filings and typical company documents |
| D19 | Audit log integrity | Append-only, hash-chained per company, with "verify integrity" | Tampering is detectable, not just forbidden |
| D20 | Browser sessions | Short-lived access + rotating refresh tokens in httpOnly cookies, CSRF token | Tokens unreadable by JavaScript; refresh-token theft detectable |
| D21 | Authentication | Admins: password + mandatory passkey / TOTP / email OTP, with recovery codes. Analysts, Reviewers, Viewers: account created by the Company Admin with an initial password, then email + password or email OTP | Strong protection where privileges are high, flexible sign-in for everyday users |
| D22 | Platform Admin access to company content | Break-glass only: written reason, time-limited, read-only, audited, Company Admin notified | Realistic privacy model while still allowing support and debugging |
| D23 | Tenant isolation | Application-level scoping + Postgres Row-Level Security + cross-tenant test suite | Defence in depth — a single bug can't leak data |
| D24 | API style | REST + JSON, OpenAPI docs, SSE for live updates, company always taken from the session | Simple, well-documented, and safe by construction |
| D25 | Experiment tracking | Weights & Biases (free tier), public dashboards | Works from Kaggle/Colab with no setup; shareable evidence |
| D26 | Publishing | All trained models and built datasets public on Hugging Face Hub with cards | Verifiable, reusable results |
| D27 | Writer training data | Distilled from a larger open-weight teacher on free GPUs, filtered by our own verifiers; DPO pairs labelled by the verifiers | No paid APIs or human labellers needed |
| D28 | Rule-matcher evaluation | Measured on held-out rules never seen in training | Proves it generalises to companies' custom rules |
| D29 | Model release | Candidate → evaluation gate (no regression) → active; one-click rollback | Safe, auditable model updates |
| D30 | Repository layout | Monorepo: apps/, services/, ml/, packages/, infra/ | One place for code, models, and infra; easy to keep in sync |
| D31 | Public demo hosting | Oracle Cloud Always Free ARM VM, Docker Compose, Caddy HTTPS | Runs the full stack free; multi-arch images required |
| D32 | CI/CD | GitHub Actions: tests, isolation suite, ML smoke eval, scans; manual-approval deploy | Free for public repos; regressions blocked before merge |
| D33 | Monitoring | Prometheus + Grafana, dashboards as code, ML score-drift alerts | Free, standard, and covers both system and model health |
