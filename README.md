# MedLedger AI

MedLedger AI is an end-to-end, agentic claims intelligence prototype for healthcare workflows. It extracts structured clinical context from messy records, proposes ICD-10 codes, validates outputs with semantic verification, applies policy guardrails, and produces an audit-ready explanation trail for every decision.

It is designed for demo and stakeholder review with a UI that makes the pipeline transparent (what each agent produced, why the system decided to approve/warn/block/escalate, and how confident it is).

Core capabilities:
- Clinical entity extraction (diagnoses, procedures, medications)
- ICD-10 coding assistance
- Semantic verification (SVM) across pipeline stages (alignment/consistency/reasonability)
- Governance + guardrails (policy evaluation, refusal/escalation, alerts)
- Explainability + audit trail (template-driven explanations, trace IDs, confidence transparency)
- Denial recovery + business impact dashboard (denials → corrections → resubmissions → recovered revenue)

The UI is demo-oriented with 4 key screens:
- Claim Processing (`/claim`)
- Agent Flow Visualization (`/flow`)
- Verification + Guardrails (`/verify`)
- Business Impact Dashboard (`/impact`)

Quick demo start:
1. Start backend:
   - `cd server`
   - `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
2. Start frontend:
   - `cd client`
   - `npm install`
   - `npm run dev`
3. Open `http://localhost:5173/claim`

---

## Tech Stack

**Backend (server/)**
- FastAPI (HTTP API)
- SQLAlchemy 2.x (ORM) + SQLite by default, PostgreSQL supported via `DATABASE_URL`
- Pydantic v2 (request/response schemas)
- LangGraph (multi-step agent orchestration + traceable workflow)
- spaCy/scispaCy (clinical NLP extraction)
- RapidFuzz (string similarity for coding/matching)
- sentence-transformers + FAISS (embedding search)
- google-generativeai (Gemini fallback extraction/OCR; optional)

**Frontend (client/)**
- React
- Vite dev server + production builds
- Tailwind (via `@tailwindcss/vite`)
- ESLint
- Simple client-side routing (no react-router) via `window.history.pushState`

---

## High-Level Architecture

### Core runtime pipeline (agents + verification + governance + explainability)

```mermaid
flowchart TD
  A[Raw claim text or uploaded record] --> B[WorkflowRecord and WorkflowState]

  B --> C[ClinicalUnderstandingAgent]
  C --> C1[SVM after clinical]

  C1 --> D[CodingAgent ICD-10]
  D --> D1[SVM after coding]

  D1 --> E[PayerRuleAgent rules and validation]
  E --> E1[SVM after rules]

  E1 --> F[GovernanceLayer policy and guardrails]
  F --> G[ExplainabilityService templates and trace]

  G --> H[(ExplainabilityAuditTrail)]
  F --> I[(GovernanceAuditLog)]
  C1 --> J[(SvmAuditLog)]
  D1 --> J
  E1 --> J

  G --> K[API response decision confidence explanations trace audit_id]
```

### Denial recovery pipeline (business impact)

```mermaid
flowchart TD
  A[Claim Status Update] --> B[DenialEvent]
  B --> C["DenialManagementAgent (LangGraph)"]
  C --> D[DenialReasonEngine]
  C --> E[RootCauseEngine]
  C --> F[CorrectionEngine]
  C --> G[ResubmissionEngine]
  C --> H["LearningService (outcomes)"]
  C --> I[(Claims/Denial tables)]
  I --> J[Denial Dashboard API]
  J --> K[Business Impact UI]
```

---

## What “Explainability” Means Here

Explainability is generated from:
- **Structured workflow context** (agent outputs, SVM stage outputs, governance results)
- **Config-driven templates** (no hardcoded explanation sentences in code paths that generate explanations)
- **Config-driven rules** that decide what to emit and how to fill template parameters

Key files:
- Templates: [server/app/config/explainability_templates.json](server/app/config/explainability_templates.json)
- Rules: [server/app/config/explainability_rules.json](server/app/config/explainability_rules.json)
- Engine: [server/app/layers/explainability_layer/explanation_engine.py](server/app/layers/explainability_layer/explanation_engine.py)
- Service + persistence: [server/app/layers/explainability_layer/service.py](server/app/layers/explainability_layer/service.py)

Each explanation item is returned as structured JSON:
```json
{
  "type": "clinical|coding|rule|policy|svm|svm_verification|decision|denial|...",
  "explanation": "Rendered from template",
  "confidence": 0.87,
  "details": { "template_id": "...", "rule_id": "...", "params": { } }
}
```

---

## API Overview (Backend)

Base URL in dev: `http://127.0.0.1:8000`

### Health
- `GET /` basic hello
- `GET /db/health` database connectivity

### Claim processing / agentic workflow
- `POST /process` run the orchestrated pipeline and return final outputs
- `POST /process/trace` run and return a structured trace view (per-agent outputs + SVM + governance)
- `POST /process/explain` run + generate explanations + write explainability audit record
- `GET /process/explain/audit/{audit_id}` fetch full persisted explainability audit JSON

### Upload pipeline (record ingestion)
- `POST /upload` upload PDF and extract text
- `POST /upload/handwritten` upload image/PDF and OCR (optional Gemini)
- `POST /upload/text` submit text and get extracted entities + ICD matches

### Denials + business impact
- `GET /denials/dashboard` metrics + denied claim list + timeline data
- Additional denial endpoints exist for claim status/outcomes and Gmail ingestion

Routes are defined under:
- [server/app/api/routes](server/app/api/routes)

---

## Frontend (Demo Screens)

The Vite dev server proxies `/api/*` → `http://127.0.0.1:8000/*`:
- [client/vite.config.js](client/vite.config.js)

### 1) Claim Processing (`/claim`)
Upload a record or paste text and show:
- Extracted diagnoses/procedures/medications
- ICD-10 codes + match score

Key component:
- [ClinicalExtractorPanel.jsx](client/src/components/ClinicalExtractorPanel.jsx)

### 2) Agent Flow Visualization (`/flow`)
Shows:
- Clinical → Coding → Rule → Final (with confidence)
- Per-step outputs + ICD table

Key component:
- [AgentWorkflowPanel.jsx](client/src/components/AgentWorkflowPanel.jsx)

### 3) Verification + Guardrail Panel (`/verify`)
Shows:
- SVM stage results (scores/issues/claims)
- Governance policy triggers + alerts
- Claim explanation panel (template-driven explanations + expandable details + audit JSON fetch)

Key components:
- [AgentWorkflowPanel.jsx](client/src/components/AgentWorkflowPanel.jsx)
- [ClaimExplanationPanel.jsx](client/src/components/ClaimExplanationPanel.jsx)

### 4) Business Impact Dashboard (`/impact`)
Shows:
- ₹ revenue recovered
- % denial reduction
- % automation
- Denied claims table + timeline

Key components:
- [Denials.jsx](client/src/pages/Denials.jsx)
- [DenialRecoveryPanel.jsx](client/src/components/DenialRecoveryPanel.jsx)

Navigation and routes:
- [client/src/App.jsx](client/src/App.jsx)

---

## Setup (Clean Instructions)

### Prerequisites
- Python 3.10+ recommended
- Node.js 18+ recommended

### 1) Backend (FastAPI)

From `server/`:

```bash
python -m venv venv
```

Windows PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run API:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Database notes:
- By default the app uses SQLite at `sqlite:///./.tmp/medledger.db` (auto-created).
- To use Postgres, set `DATABASE_URL`:
  - Example: `postgresql://user:pass@localhost:5432/medledger`

### 2) Frontend (React + Vite)

From `client/`:

```bash
npm install
npm run dev
```

Open:
- `http://localhost:5173/`

---

## Environment Variables (Optional)

**Database**
- `DATABASE_URL` or `DB_URL`

**Gemini (optional LLM/OCR fallback)**
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_VISION_MODEL`

**Gmail ingestion (optional)**
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_USER_ID` (default: `me`)

---

## Testing

Backend tests:
```bash
cd server
pytest -q
```

Frontend checks:
```bash
cd client
npm run lint
npm run build
```

---

## Repository Structure

```
client/                 # React UI (4 demo screens)
server/
  app/
    api/routes/         # FastAPI endpoints
    layers/             # Pipeline modules (agents, SVM, governance, explainability, denials)
    models/             # SQLAlchemy models
    schemas/            # Pydantic schemas
    config/             # JSON-driven rules/templates/thresholds
    db/                 # DB session + init
  tests/                # pytest suite
```

---

## Troubleshooting

- Frontend calls fail with 404:
  - Ensure backend is running on `127.0.0.1:8000`
  - Ensure Vite proxy is enabled: [vite.config.js](client/vite.config.js)
- DB errors:
  - Check `GET /db/health`
  - If using Postgres, verify `DATABASE_URL` and connectivity
- Gemini features not working:
  - Set `GEMINI_API_KEY` (and optionally model env vars)
