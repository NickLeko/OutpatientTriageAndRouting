# Triage Routing MVP 

A small Streamlit MVP that collects structured intake inputs and returns a deterministic routing recommendation:
**ED / Urgent Care / PCP / Self-care**.

This is a demo to showcase product + workflow thinking in healthcare triage. It is **not** medical advice.

## What it does
- Structured intake form (symptoms, red flags, risk history, optional vitals)
- Deterministic routing engine (`route_patient`) with explicit reasons
- Injury/wound branch with conditional questions
- No LLM in v1 (by design)

## Safety stance
- **Rules decide.** The routing output comes from deterministic logic only.
- If an LLM layer is added later, it must:
  - summarize inputs
  - explain the rule-based routing
  - list escalation triggers
  - **never override the route**

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py


![CI](https://github.com/<your-username>/<repo-name>/actions/workflows/ci.yml/badge.svg)
