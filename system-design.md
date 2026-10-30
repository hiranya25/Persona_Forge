# Persona Forge — System Design

> Status: **In progress** — written section by section, each one reviewed and
> approved before it lands here. Sections marked _TBD_ are not designed yet.

## Contents

1. [Overview & goals](#1-overview--goals)
2. [Users, roles & portals](#2-users-roles--portals)
3. [Features per portal](#3-features-per-portal)
4. [High-level architecture](#4-high-level-architecture)
5. [AI/ML pipeline](#5-aiml-pipeline)
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
| **M6** | Writer | Persona prompt + passages → cited answer | Small open-weight instruct LLM (1.5B–4B) | **Yes** — QLoRA SFT, then DPO | GGUF Q4 via Ollama |

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
