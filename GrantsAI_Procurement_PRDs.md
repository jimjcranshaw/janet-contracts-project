# Grants AI – Public Procurement Features (PRDs)

**Target:** Add a new “Contracts” capability inside Grants AI (UK public procurement), built on an **Azure PostgreSQL SQL DB** (Azure Database for PostgreSQL Flexible Server) with **RAG via `pgvector`**.

**Core data sources**
- Find a Tender (OCDS JSON – release packages + record packages)
- Contracts Finder (API incl. VCSE/SME suitability flags where available)

---

## PRD 01 — Procurement Data Ingestion & Normalisation Layer

### Overview
Build a robust ingestion pipeline and schema that continuously pulls UK procurement notices/awards into an **Azure Postgres** warehouse, normalises buyers/suppliers, and supports downstream features: matching, alerts, expiry intelligence, trends, and RAG on tender docs.

### Problem
Charities/VCSEs lack a low-cost way to build a living opportunity database that supports proactive pipeline building (not just reactive searching).

### Goals
- Ingest Find a Tender OCDS **release packages** and **record packages** into Postgres.
- Ingest Contracts Finder data via its API endpoints / feeds where available.
- Maintain an **incremental change log** (OCDS releases) to support “what changed since yesterday?” and accurate alerts.
- Provide a stable, queryable model for downstream modules.

### Non-goals
- Full competitor intelligence / pricing estimation.
- Replacing external tender portals’ entire UI.

### Primary users
- Grants AI users in UK charities/VCSEs doing contract bidding.
- Internal Grants AI ops (support & QA).

### Functional requirements
1. **Connectors**
   - Find a Tender OCDS Release Package pull (scheduled).
   - Find a Tender OCDS Record Package pull (scheduled).
   - Contracts Finder feed/API pull (scheduled).
2. **Incremental updates**
   - Store raw JSON and parsed structured fields.
   - Idempotent upserts keyed by OCID + release id (where present).
3. **Normalisation**
   - Buyer identity resolution (canonical buyer table + aliases).
   - Supplier identity resolution for awarded contracts (canonical supplier table + aliases).
   - Location normalisation (region/LA/ICB where derivable; keep raw too).
4. **Observability**
   - Ingestion job status, lag, error counts, schema drift detection.
5. **Data quality checks**
   - Required field presence checks.
   - Deduplication rules for repeated releases/records.

### Data model (high-level)
- `notice_raw` (source, fetched_at, raw_json, hash)
- `ocds_release` (ocid, release_id, release_date, tag, parsed fields…)
- `ocds_record` (ocid, compiled_record_json, updated_at…)
- `buyer` (buyer_id, canonical_name, identifiers, address fields, alias table)
- `supplier` (supplier_id, canonical_name, identifiers, alias table)
- `contract_award` (ocid, award_id, supplier_id, value, dates, etc.)
- `notice_attachment` (metadata, storage URI, text extraction status)
- `embedding` (doc_id, chunk_id, vector, metadata JSONB) — via `pgvector`

### Technical requirements
- Azure Postgres + `pgvector` enabled.
- Use JSONB for forward compatibility (retain full source payloads).
- Store large original documents in Azure Blob; keep pointers + hashes in Postgres.
- Ingestion via scheduled jobs (Azure Functions / Container Apps / Data Factory – implementation choice).

### Acceptance criteria
- 99%+ ingestion job success over 30 days.
- <24h ingestion lag for notices.
- Deterministic upsert behaviour (no duplicate OCIDs in structured tables).
- Ability to answer: “all notices for buyer X in last 12 months”, “awards with end dates in next 9 months”.

### KPIs
- Ingestion lag (p50/p95)
- Parse success rate
- Duplicate rate
- Buyer/supplier match confidence distribution

### Risks & mitigations
- **Schema drift:** store raw JSON; parse via versioned mappers; alert on new fields.
- **Rate limits / downtime:** backoff + checkpointing.

---

## PRD 02 — VCSE Service Profile & Taxonomy Mapping

### Overview
Add a “Service Profile” layer to Grants AI that represents what a charity can deliver (capabilities, geographies, constraints), mapped to commissioning language and procurement classifications.

### Problem
Generic keyword search produces irrelevant tenders; VCSEs need “match to what we can deliver, compliantly, at our scale”.

### Goals
- Capture a VCSE’s service footprint (who/what/where/how).
- Provide a taxonomy aligned to commissioning language (configurable over time).
- Map procurement classifications (e.g., CPV/other codes where available) into the VCSE taxonomy.
- Generate a match score used by alerts and opportunity ranking.

### Non-goals
- Fully automated service-profile creation without user confirmation.
- Full CRM build.

### User stories
- “As a charity, I want to set my delivery areas and service types so the platform only shows realistic opportunities.”
- “As a bid lead, I want to exclude tenders that are too large or require regulated activities we don’t do.”

### Functional requirements
- Service Profile UI embedded in Grants AI settings:
  - Service areas (geo)
  - Beneficiary groups
  - Delivery model constraints (in-house, subcontract, consortium)
  - Contract size comfort bands
  - Compliance capabilities (safeguarding, ISO, Cyber Essentials, etc. – configurable)
- Matching engine:
  - Classification match (where present)
  - Semantic match (embeddings over notice text)
  - Rule-based gating (hard filters)

### Data requirements
- `org_service_profile` (JSONB + typed columns for key facets)
- `taxonomy_node` + `org_taxonomy_selection`
- `match_score` materialised view per org × notice

### Acceptance criteria
- User can configure a profile in <20 minutes.
- ≥50% reduction in user-hidden/irrelevant notices vs baseline keyword feed (pilot cohort).
- Hard gating excludes disallowed opportunities.

---

## PRD 03 — VCSE Suitability & Bid/No-Bid Gate

### Overview
A structured “bid/no-bid” assistant tuned for VCSE reality, producing an explainable recommendation and an action checklist.

### Problem
VCSEs waste time on bids they can’t win or can’t deliver safely (scale, mobilisation, compliance burden, TUPE exposure, safeguarding requirements).

### Goals
- Provide a fast qualification view: **Go / Caution / No-go** with reasons.
- Make risks explicit and actionable.

### Functional requirements
- Inputs: notice fields + any uploaded tender pack docs + org profile.
- Outputs:
  - Eligibility checklist (pass/fail)
  - Risk flags (TUPE likelihood, safeguarding/regulated activity, mobilisation timeline, data handling)
  - Evidence checklist (policies/certs needed)
  - Recommendation + confidence + “why”
- Explainability: show which signals drove the decision.

### Data & logic
- Rule engine + ML signals:
  - Rules: thresholds, required accreditations, mandatory insurance, hard deadlines.
  - ML: semantic cues in docs that imply large-prime requirements or heavy reporting.
- Store decisions and outcomes to learn over time.

### Acceptance criteria
- >70% of “No-go” recommendations accepted without override (pilot).
- Each recommendation includes at least 5 concrete, tender-specific reasons/actions.

---

## PRD 04 — Opportunity Feed, Alerts & “Changes Since Last Time”

### Overview
A Grants AI “Contracts” feed that pushes relevant opportunities and meaningful changes (not noise), based on OCDS change history.

### Problem
Tender monitoring is noisy. VCSEs need: “Tell me what matters, when it matters.”

### Goals
- Personalised feed ranked by profile match + suitability.
- Alerts for:
  - New relevant notice
  - Material change to a tracked notice (date/value/spec change)
  - Early engagement relevant to the org
- Use OCDS releases to detect change deltas.

### Functional requirements
- Alerts channels: in-app + email (optional) + webhook (later).
- “Track notice” capability.
- “What changed” diff view between releases.

### Acceptance criteria
- Users mark <20% of alerts as “not relevant”.
- Change detection correctly identifies deadline changes and value changes where present.

---

## PRD 05 — Contract Renewal / Expiry Intelligence

### Overview
Forecast re-tender windows using awards and contract date fields, showing “when to start relationship-building”.

### Problem
VCSEs often arrive too late; incumbents have a structural advantage.

### Goals
- Build an expiry calendar for buyers/categories relevant to the org.
- Provide “runway” nudges: 12/9/6/3 months to likely procurement activity.

### Functional requirements
- Identify contracts likely to re-tender based on:
  - End dates + extension options (if published)
  - Buyer historic procurement patterns
- Surface:
  - Incumbent supplier(s)
  - Approx contract value band
  - Likely route (open tender vs framework/DPS) inferred from buyer history
- Alerts: “Contract likely to re-tender in ~6 months”.

### Data requirements
- `contract_timeline` (start/end, extensions, confidence)
- Buyer “procurement pattern” features (route mix, typical lotting, cadence)

### Acceptance criteria
- For a set of known re-tenders (manually validated), the system flags the opportunity window at least 3 months in advance in >60% of cases (v1 target).

---

## PRD 06 — Commissioning Trend & Packaging Shift Analytics

### Overview
Dashboards that detect how services are being packaged and bought over time (bundling, lotting, route-to-market changes), filtered to the org’s service taxonomy.

### Problem
VCSEs miss opportunities when services move into different structures (frameworks, larger bundles, different buyer departments).

### Goals
- Provide market-shaping intelligence that changes bidding strategy.

### Functional requirements
- Dashboards:
  - Spend/value trend by taxonomy area
  - Lot size distribution shifts
  - Route-to-market trend (open vs framework vs DPS where detectable)
  - Buyer behaviour: new entrants, switching incumbents, VCSE share signals where inferable
- “Insight cards” with recommended actions (e.g., “consider consortium route; bundles increasing”).

### Data requirements
- Time-series aggregates (materialised views)
- Classifier outputs stored for auditability (why something was categorised)

### Acceptance criteria
- At least 3 actionable insight cards per month for an active pilot org.
- Users confirm ≥1 strategy change within 8 weeks of using dashboards (qualitative KPI).

---

## PRD 07 — Tender Pack RAG & Requirement Extraction

### Overview
Document ingestion + chunking + embeddings in Postgres (`pgvector`), enabling: summarisation, requirement extraction, Q&A, and “common questions” learning — primarily via **user-uploaded packs** (safe default).

### Problem
Tender packs are long, repetitive, and easy to misread; VCSE bid teams are time-poor.

### Goals
- Reduce time to understand a tender pack.
- Extract hard requirements and evaluation criteria reliably.

### Functional requirements
- Upload tender pack docs (PDF/Word/Excel where feasible).
- Pipeline:
  - Extract text
  - Chunk
  - Embed + store vectors in Postgres
  - Generate:
    - Executive summary
    - Mandatory requirements list (pass/fail)
    - Evaluation criteria map (question → weighting if present)
    - Compliance checklist
    - Clarification questions list
- Q&A chat scoped to the tender pack + org evidence bank.

### Technical requirements
- `pgvector` in Azure Postgres.
- Strong document provenance: citations to page/section in outputs.
- Guardrails: never invent requirements; show “not found” where absent.

### Acceptance criteria
- Requirement list includes page references for ≥90% of extracted requirements.
- Users report ≥30% reduction in time to first bid/no-bid decision.

---

## PRD 08 — Social Value & Outcomes Builder

### Overview
A VCSE-native module that turns tender social value asks into credible, measurable commitments and reusable evidence, integrated with bid drafting.

### Problem
Social value responses are often generic or overpromised; commissioners expect structured outcomes and measurement.

### Goals
- Produce believable commitments tied to the VCSE’s actual services and geography.
- Build a reusable social value library across bids.

### Functional requirements
- Social value template library (configurable by commissioner/sector).
- Evidence prompts: case studies, policies, local partnerships, data.
- Commitment generator with guardrails:
  - Must be measurable
  - Must be deliverable within contract scope
  - Must avoid invented baselines
- Tracking hooks (later): record commitments for reporting.

### Acceptance criteria
- Generated commitments pass an internal credibility check (no impossible numbers; aligns to delivery model).
- Users reuse ≥30% of social value content across bids after 3 tenders.

---

## PRD 09 — Consortium Builder & Partner Fit

### Overview
Enable VCSEs to form credible consortia for larger/bundled contracts using structured partner-fit, gap analysis, and lightweight collaboration artefacts.

### Problem
Many VCSEs can only win by partnering, but partner search and consortium structuring is slow and ad hoc.

### Goals
- Make consortium formation a first-class workflow inside Grants AI.

### Functional requirements
- Opportunity gap analysis: what capabilities/compliance/scale are missing.
- Partner suggestions:
  - From a directory (v1: user-managed; later: external enrichment)
  - By geography + taxonomy + compliance tags
- Consortium archetypes + artefact generation:
  - Draft roles/responsibilities matrix
  - Draft MoU/Heads of Terms outline
  - Joint delivery narrative skeleton
- Sharing permissions for opportunity packs with partners (read-only links).

### Acceptance criteria
- Users can create a consortium plan (roles + gaps + next steps) in <60 minutes.
- At least one consortium invite sent for ≥20% of “too large solo” opportunities in pilot cohort.

---

# Integration into Grants AI

## Product surface
Add a new area: **Contracts** (alongside Grants/Funders), sharing:
- Organisation profile (extended to Service Profile)
- Evidence bank (shared docs and structured assets)
- Drafting UI patterns (like grants, but tender-specific structures)

## Shared platform components
- One ingestion/warehouse for all organisations (multi-tenant with strict isolation)
- One RAG layer (Azure Postgres + `pgvector`) used across grants and tenders

## Key architectural decision
**Azure Postgres is the system of record.** Raw JSON and normalised tables live in Postgres; large files live in Blob Storage with hashes and pointers stored in Postgres; vectors live in Postgres via `pgvector`.
