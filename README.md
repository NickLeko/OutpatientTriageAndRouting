# Outpatient Triage & Care Routing MVP

## What this is
Outpatient Triage & Routing is a demo MVP that collects structured symptom and vitals history and returns a **care-setting recommendation**:

- **ED** (Immediate)
- **Urgent Care** (Same day)
- **Primary Care (PCP)** (24–72 hrs)
- **Self-care** (Monitor)

This project is **not medical advice** and does not provide diagnoses.  
It is intended as a **product and engineering demonstration**, not a consumer medical tool.

---

## Key design: deterministic routing + LLM explanation (separated)
This app intentionally separates **decision** from **explanation**:

### 1) Deterministic routing engine (auditable)
- Implemented as a rule-based function (`triage/routing.py`)
- Produces: `route`, `urgency`, and explicit `reasons`
- This is the only component allowed to decide ED vs UC vs PCP vs Self-care

### 2) LLM explanation layer (cannot change routing)
- Runs *after* routing is decided
- Receives the finalized route + rule reasons
- Generates patient-friendly wording only
- Prompt is explicitly constrained to never contradict the route

This separation is deliberate for safety, debuggability, and product credibility.

---

## Exports
After submission, the app generates:
- **Patient summary (.txt)** (LLM explanation)
- **Clinician summary (.txt)** (structured inputs + routing + reasons)
- **Share package (.zip)** bundling:
  - `patient_summary_<encounter>.txt`
  - `clinician_summary_<encounter>.txt`
  - `inputs_<encounter>.json`

Each run includes an **Encounter ID + timestamp** for traceability.

---

## Testing & CI
- **In-app sanity matrix** for rapid regression checks
- **Pytest unit tests** (`tests/`)
- **GitHub Actions CI** runs tests on every push and pull request

---

## Run locally (optional)
```bash
pip install -r requirements.txt
streamlit run app.py


## Data & Privacy Notes
- This prototype is intended for **demonstration with synthetic/example data only**
- Do **not** enter real patient identifiers or protected health information (PHI)
- No persistence, EHR integration, or clinical validation is implemented

