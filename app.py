# app.py
# MVP: Outpatient Triage & Routing

# Run:
#   pip install streamlit
#   streamlit run app.py

# Notes:
# - This app does NOT provide medical advice. It demonstrates routing logic for an MVP.
# - Routing is deterministic and auditable. LLM (if added) must NEVER override routing.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import streamlit as st

import os
from typing import Any
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from datetime import datetime, timezone
import uuid

from triage.routing import route_patient, RoutingResult

import io
import json
import zipfile


# -----------------------------
# Constants / Options
# -----------------------------
CHIEF_COMPLAINTS = [
    "Chest pain / pressure",
    "Shortness of breath",
    "Abdominal pain",
    "Headache",
    "Fever / infection symptoms",
    "Cough / sore throat",
    "Urinary symptoms",
    "Back pain",
    "Rash / skin issue",
    "Nausea / vomiting / diarrhea",
    "Injury / wound",
    "Other",
]

ONSET_OPTIONS = [
    "< 6 hours",
    "6–24 hours",
    "1–3 days",
    "4–7 days",
    "> 7 days",
]

TREND_OPTIONS = ["Better", "Same", "Worse"]

HAPPENED_BEFORE_OPTIONS = ["Yes — similar symptoms before", "No — first time", "Not sure"]

FEVER_OPTIONS = ["Yes", "No", "Don’t know / can’t check"]

SEX_OPTIONS = ["Female", "Male", "Intersex", "Prefer not to say"]

PREGNANCY_OPTIONS = ["Yes", "No", "Not applicable"]

RISK_CONDITIONS = [
    "Heart disease / prior heart attack",
    "Stroke / TIA history",
    "Diabetes",
    "Chronic lung disease (asthma/COPD)",
    "Kidney disease",
    "Immunocompromised (chemo, transplant, HIV, long-term steroids)",
    "None of the above",
]

RED_FLAGS = [
    "Trouble breathing at rest",
    "Fainting / nearly fainted",
    "New confusion",
    "Severe chest pain/pressure",
    "Blue lips/face",
    "Uncontrolled bleeding",
    "Signs of stroke (face droop, arm weakness, speech trouble)",
    "Severe allergic reaction (swelling of lips/tongue, hives + breathing trouble)",
    "Severe dehydration (unable to keep fluids down, very little urine)",
    "Severe abdominal pain with rigid belly",
    "Worst headache of life / sudden thunderclap headache",
    "High fever with stiff neck or rash",
    "Pregnancy + bleeding or severe abdominal pain",
]

INJURY_TYPES = [
    "Joint (ankle, knee, shoulder, wrist, etc.)",
    "Muscle strain / pull",
    "Cut / laceration",
    "Burn",
    "Bruise / swelling",
    "Unsure",
]

INJURY_LOCATIONS = [
    "Ankle",
    "Knee",
    "Wrist",
    "Shoulder",
    "Hand",
    "Foot",
    "Head",
    "Other",
]

INJURY_MECHANISMS = [
    "Sports / exercise",
    "Fall",
    "Accident",
    "Cut / sharp object",
    "Other",
]

INJURY_FLAGS = [
    "Severe swelling",
    "Obvious deformity",
    "Unable to bear weight or use limb",
    "Numbness or tingling",
    "Bone visible or deep open wound",
    "Bleeding that won’t stop after 10 minutes of firm pressure",
]



# -----------------------------
# Helpers
# -----------------------------

def apply_preset(preset: Dict) -> None:
    """
    Write preset values into Streamlit session_state so widgets update.
    IMPORTANT: keys must match widget `key=` values.
    """
    for k, v in preset.items():
        st.session_state[k] = v



def run_routing_tests() -> List[Dict[str, Any]]:
    """
    Runs a small deterministic test suite against route_patient().
    Returns rows for display.
    """
    tests = [
    {
        "name": "A — ED (red flag chest pain)",
        "inputs": {
            "age": 58,
            "sex": "Male",
            "pregnant": "Not applicable",
            "chief_complaint": "Chest pain / pressure",
            "onset": "6–24 hours",
            "severity_0_10": 8,
            "trend": "Worse",
            "happened_before": "No — first time",
            "fever": "No",
            "red_flags": ["Severe chest pain/pressure"],
            "conditions": ["Heart disease / prior heart attack"],
            "temp_f": None,
            "hr": None,
            "spo2": None,
            "pcp_access": "Yes",
            "urgent_access": "Yes",
            "injury_type": None,
            "injury_location": None,
            "injury_mechanism": None,
            "injury_flags": [],
        },
        "expect_route": "ED",
    },
    {
        "name": "B — Urgent (fever + immunocompromised)",
        "inputs": {
            "age": 45,
            "sex": "Female",
            "pregnant": "No",
            "chief_complaint": "Fever / infection symptoms",
            "onset": "1–3 days",
            "severity_0_10": 6,
            "trend": "Worse",
            "happened_before": "Not sure",
            "fever": "Yes",
            "red_flags": [],
            "conditions": ["Immunocompromised (chemo, transplant, HIV, long-term steroids)"],
            "temp_f": 101.6,
            "hr": 105,
            "spo2": 96,
            "pcp_access": "Yes",
            "urgent_access": "Yes",
            "injury_type": None,
            "injury_location": None,
            "injury_mechanism": None,
            "injury_flags": [],
        },
        "expect_route": "Urgent Care",
    },
    {
        "name": "C — PCP (mild cough, stable, PCP access)",
        "inputs": {
            "age": 29,
            "sex": "Male",
            "pregnant": "Not applicable",
            "chief_complaint": "Cough / sore throat",
            "onset": "6–24 hours",
            "severity_0_10": 2,
            "trend": "Same",
            "happened_before": "Yes — similar symptoms before",
            "fever": "Don’t know / can’t check",
            "red_flags": [],
            "conditions": [],
            "temp_f": None,
            "hr": None,
            "spo2": None,
            "pcp_access": "Yes",
            "urgent_access": "Yes",
            "injury_type": None,
            "injury_location": None,
            "injury_mechanism": None,
            "injury_flags": [],
        },
        "expect_route": "PCP",
    },
    {
        "name": "D — Injury Urgent (can't bear weight)",
        "inputs": {
            "age": 33,
            "sex": "Male",
            "pregnant": "Not applicable",
            "chief_complaint": "Injury / wound",
            "onset": "< 6 hours",
            "severity_0_10": 6,
            "trend": "Worse",
            "happened_before": "No — first time",
            "fever": "No",
            "red_flags": [],
            "conditions": [],
            "temp_f": None,
            "hr": None,
            "spo2": None,
            "pcp_access": "No",
            "urgent_access": "Yes",
            "injury_type": "Joint (ankle, knee, shoulder, wrist, etc.)",
            "injury_location": "Ankle",
            "injury_mechanism": "Sports / exercise",
            "injury_flags": ["Unable to bear weight or use limb"],
        },
        "expect_route": "Urgent Care",
    },
]

    rows: List[Dict[str, Any]] = []
    for t in tests:
        res = route_patient(t["inputs"])
        passed = (res.route == t["expect_route"])
        rows.append(
            {
                "Test": t["name"],
                "Expected": t["expect_route"],
                "Got": res.route,
                "Urgency": res.urgency,
                "Pass": "✅" if passed else "❌",
            }
        )
    return rows


def parse_optional_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
def format_patient_export(explanation: str, inputs: Dict[str, Any]) -> str:
    header = [
        "PATIENT SUMMARY (MVP DEMO — NOT MEDICAL ADVICE)",
        f"Encounter ID: {inputs.get('encounter_id')}",
        f"Timestamp: {inputs.get('encounter_ts')}",
        "",
    ]
    return ("\n".join(header) + (explanation or "").strip()).strip()


def format_clinician_export(inputs: Dict[str, Any], result: RoutingResult) -> str:
    """
    Clinician-facing structured summary.
    Deterministic, auditable, no LLM prose.
    """

    red_flags = inputs.get("red_flags") or []
    conditions = inputs.get("conditions") or []
    injury_flags = inputs.get("injury_flags") or []

    lines = [
        "CLINICIAN SUMMARY (MVP DEMO — NOT MEDICAL ADVICE)",
        f"Encounter ID: {inputs.get('encounter_id')}",
        f"Timestamp: {inputs.get('encounter_ts')}",
        "",
        f"Recommended care: {result.route} ({result.urgency})",
        "",
        "Rule-based reasons:",
    ]

    if result.reasons:
        lines.extend([f"- {reason}" for reason in result.reasons])
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "Structured inputs:",
            f"- Age: {inputs.get('age')}",
            f"- Sex: {inputs.get('sex')}",
            f"- Pregnant: {inputs.get('pregnant')}",
            f"- Chief complaint: {inputs.get('chief_complaint')}",
            f"- Onset: {inputs.get('onset')}",
            f"- Severity (0–10): {inputs.get('severity_0_10')}",
            f"- Trend: {inputs.get('trend')}",
            f"- Happened before: {inputs.get('happened_before')}",
            f"- Fever: {inputs.get('fever')}",
            f"- Red flags selected: {red_flags if red_flags else 'None'}",
            f"- Conditions selected: {conditions if conditions else 'None'}",
            f"- Vitals (if known): temp_f={inputs.get('temp_f')}, hr={inputs.get('hr')}, spo2={inputs.get('spo2')}",
            f"- Injury type: {inputs.get('injury_type') or 'None'}",
            f"- Injury location: {inputs.get('injury_location') or 'None'}",
            f"- Injury mechanism: {inputs.get('injury_mechanism') or 'None'}",
            f"- Injury flags: {injury_flags if injury_flags else 'None'}",
            "",
            "Disclaimer:",
            "This summary is generated for demonstration purposes only and is not medical advice.",
        ]
    )

    return "\n".join(lines).strip()

def build_share_package_zip(encounter_id, patient_txt, clinician_txt, inputs):
    """
    Build a ZIP file (in memory) that contains:
    - patient summary
    - clinician summary
    - raw inputs JSON
    """
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        if patient_txt:
            zipf.writestr(
                f"patient_summary_{encounter_id}.txt",
                patient_txt
            )

        zipf.writestr(
            f"clinician_summary_{encounter_id}.txt",
            clinician_txt
        )

        zipf.writestr(
            f"inputs_{encounter_id}.json",
            json.dumps(inputs, indent=2)
        )

    return buffer.getvalue()


def parse_optional_int(s: str) -> Optional[int]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None

def llm_enabled() -> bool:
    """
    LLM is enabled only if:
    - OpenAI SDK is installed
    - OPENAI_API_KEY is present in env
    """
    if OpenAI is None:
        return False

    return bool(os.getenv("OPENAI_API_KEY", "").strip())

def generate_llm_explanation(prompt: str) -> str:
    """
    Calls OpenAI to generate a patient-facing explanation.
    Routing is already decided and MUST NOT be changed.
    """
    try:
        client = OpenAI()  # reads OPENAI_API_KEY from env

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a healthcare navigation assistant. "
                        "You do NOT diagnose or change routing decisions. "
                        "You ONLY explain the already-decided route."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
            max_tokens=300,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"LLM explanation unavailable due to an error: {e}"

def build_explanation_prompt(inputs: Dict[str, Any], routing: RoutingResult) -> str:
    """
    Strict prompt: explanation only. Never override route.
    """
    red_flags = inputs.get("red_flags", [])
    conditions = inputs.get("conditions", [])
    injury_flags = inputs.get("injury_flags", [])

    return f"""
You are a healthcare navigation assistant.
You DO NOT diagnose conditions.
You MUST NOT change or contradict the routing decision.

Routing decision (FINAL): {routing.route}
Urgency (FINAL): {routing.urgency}
Rule-based reasons: {", ".join(routing.reasons) if routing.reasons else "None provided"}

User inputs (structured):
- Age: {inputs.get("age")}
- Sex: {inputs.get("sex")}
- Pregnant: {inputs.get("pregnant")}
- Chief complaint: {inputs.get("chief_complaint")}
- Onset: {inputs.get("onset")}
- Severity (0–10): {inputs.get("severity_0_10")}
- Trend: {inputs.get("trend")}
- Happened before: {inputs.get("happened_before")}
- Fever: {inputs.get("fever")}
- Red flags selected: {red_flags if red_flags else "None"}
- Conditions selected: {conditions if conditions else "None"}
- Vitals (if known): temp_f={inputs.get("temp_f")}, hr={inputs.get("hr")}, spo2={inputs.get("spo2")}
- Injury flags (if any): {injury_flags if injury_flags else "None"}

Write a patient-facing explanation with these STRICT rules:

1) Start with:
   "Recommended care: <ROUTE> (<URGENCY>)"
   Use the FINAL route exactly as written above.

2) Briefly explain WHY using only the rule-based reasons and user inputs.
   Do NOT introduce new symptoms, diagnoses, or probabilities.

3) Include a "Watch-outs" section with 4–6 bullets.
   You MUST include:
   - Trouble breathing at rest
   - Signs of stroke (face droop, arm weakness, speech difficulty)
   - Fainting or near-fainting
   - Worsening chest pain or pressure

4) Include a "What to do next" section with 3–6 bullets.
   - Actions must match the FINAL route.
   - You may suggest basic safety steps (rest, avoid exertion).
   - If mentioning hydration, qualify it clearly:
     "If it does not delay care and you are not vomiting."

5) End with a short disclaimer:
   "This is not medical advice. If this is an emergency, call local emergency services."

Keep the total response under 220 words.
""".strip()


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Triage Routing MVP", page_icon="🩺", layout="centered")
st.markdown(
    """
    <style>
      /* Force the main app area to be scrollable on mobile/webviews */
      html, body, [data-testid="stAppViewContainer"] {
        height: 100%;
        overflow: auto !important;
        -webkit-overflow-scrolling: touch !important;
      }

      /* Streamlit sometimes wraps the main block in a container that can clip overflow */
      [data-testid="stAppViewContainer"] > .main {
        overflow: auto !important;
        -webkit-overflow-scrolling: touch !important;
      }

      /* Reduce chances of scroll-jank with sticky headers */
      header[data-testid="stHeader"] {
        position: relative !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🩺 Triage Routing MVP")
st.caption("Rules-based routing. LLM explanation layer can be added later (must not override rules).")

with st.expander("Safety & Scope (read)", expanded=True):
    st.markdown(
        """
- This app is a **demo MVP** and **not medical advice**.
- Routing is **deterministic** and based solely on user inputs.
- If you believe you are experiencing an emergency, **call local emergency services**.
"""
    )

st.subheader("Quick Test Presets")

PRESETS = {
    "Person A — ED (red flag chest pain)": {
        "age": 58,
        "sex": "Male",
        "pregnant": "Not applicable",
        "chief_complaint": "Chest pain / pressure",
        "onset": "6–24 hours",
        "severity_0_10": 8,
        "trend": "Worse",
        "happened_before": "No — first time",
        "fever": "No",
        "red_flags": ["Severe chest pain/pressure"],
        "conditions": ["Heart disease / prior heart attack"],
        "temp_f_raw": "",
        "hr_raw": "",
        "spo2_raw": "",
        "pcp_access": "Yes",
        "urgent_access": "Yes",
        "injury_type": None,
        "injury_location": None,
        "injury_mechanism": None,
        "injury_flags": [],
    },
    "Person B — Urgent Care (fever + immunocompromised)": {
        "age": 45,
        "sex": "Female",
        "pregnant": "No",
        "chief_complaint": "Fever / infection symptoms",
        "onset": "1–3 days",
        "severity_0_10": 6,
        "trend": "Worse",
        "happened_before": "Not sure",
        "fever": "Yes",
        "red_flags": [],
        "conditions": ["Immunocompromised (chemo, transplant, HIV, long-term steroids)"],
        "temp_f_raw": "101.6",
        "hr_raw": "105",
        "spo2_raw": "96",
        "pcp_access": "Yes",
        "urgent_access": "Yes",
        "injury_type": None,
        "injury_location": None,
        "injury_mechanism": None,
        "injury_flags": [],
    },
    "Person C — Self-care (mild cough)": {
        "age": 29,
        "sex": "Male",
        "pregnant": "Not applicable",
        "chief_complaint": "Cough / sore throat",
        "onset": "6–24 hours",
        "severity_0_10": 2,
        "trend": "Same",
        "happened_before": "Yes — similar symptoms before",
        "fever": "Don’t know / can’t check",
        "red_flags": [],
        "conditions": ["None of the above"],
        "temp_f_raw": "",
        "hr_raw": "",
        "spo2_raw": "",
        "pcp_access": "Yes",
        "urgent_access": "Yes",
        "injury_type": None,
        "injury_location": None,
        "injury_mechanism": None,
        "injury_flags": [],
    },
    "Person D — Injury Urgent Care (can’t bear weight)": {
        "age": 33,
        "sex": "Male",
        "pregnant": "Not applicable",
        "chief_complaint": "Injury / wound",
        "onset": "< 6 hours",
        "severity_0_10": 6,
        "trend": "Worse",
        "happened_before": "No — first time",
        "fever": "No",
        "red_flags": [],
        "conditions": ["None of the above"],
        "temp_f_raw": "",
        "hr_raw": "",
        "spo2_raw": "",
        "pcp_access": "No",
        "urgent_access": "Yes",
        "injury_type": "Joint (ankle, knee, shoulder, wrist, etc.)",
        "injury_location": "Ankle",
        "injury_mechanism": "Sports / exercise",
        "injury_flags": ["Unable to bear weight or use limb"],
    },
}

# --- Quick Test Presets ---
cols = st.columns(4)
preset_names = list(PRESETS.keys())

for i, name in enumerate(preset_names):
    if cols[i % 4].button(name):
        apply_preset(PRESETS[name])
        st.toast(f"Loaded preset: {name}", icon="✅")
        st.rerun()

with st.expander("Routing test matrix (sanity checks)"):
    if st.button("Run routing tests"):
        rows = run_routing_tests()
        st.table(rows)


# --- Intake Form (starts AFTER presets) ---
with st.form("triage_form"):

    st.subheader("Step 1 — Basics")
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input(
            "Age (years)",
            min_value=0,
            max_value=120,
            value=30,
            step=1,
            key="age",
        )
        sex = st.selectbox("Sex", SEX_OPTIONS, index=0, key="sex")
    with col2:
        pregnant = st.selectbox(
            "Pregnant or could be pregnant?",
            PREGNANCY_OPTIONS,
            index=2,
            key="pregnant",
        )

    # ... keep the rest of your form fields here ...


    st.subheader("Step 2 — Symptoms")
    chief = st.selectbox("Main issue today", CHIEF_COMPLAINTS, index=5, key="chief_complaint")
    onset = st.selectbox("When did this start?", ONSET_OPTIONS, index=2, key="onset")
    severity = st.slider(
        "How severe is it right now? (0–10)", min_value=0, max_value=10, value=4, key="severity_0_10"
    )
    trend = st.selectbox("Getting better or worse?", TREND_OPTIONS, index=1, key="trend")
    happened_before = st.selectbox(
        "Has this same problem happened before?", HAPPENED_BEFORE_OPTIONS, index=2, key="happened_before"
    )
    fever = st.selectbox(
        "Do you currently have a fever (≥100.4°F / 38°C)?", FEVER_OPTIONS, index=2, key="fever"
    )

    st.subheader("Step 3 — Red Flags")
    red_flags = st.multiselect("Any of these right now?", RED_FLAGS, key="red_flags")

    st.subheader("Step 4 — Medical History")
    conditions = st.multiselect(
        "Do you have any of these conditions?",
        RISK_CONDITIONS,
        default=["None of the above"],
        key="conditions",
    )

    st.subheader("Step 5 — Vitals (optional)")
    col3, col4, col5 = st.columns(3)
    with col3:
        temp_f_raw = st.text_input("Temperature (°F)", value="", key="temp_f_raw")
    with col4:
        hr_raw = st.text_input("Heart rate (bpm)", value="", key="hr_raw")
    with col5:
        spo2_raw = st.text_input("Oxygen saturation SpO₂ (%)", value="", key="spo2_raw")

    temp_f = parse_optional_float(temp_f_raw)
    hr = parse_optional_int(hr_raw)
    spo2 = parse_optional_int(spo2_raw)

    st.subheader("Step 6 — Access (optional)")
    col6, col7 = st.columns(2)
    with col6:
        pcp_access = st.selectbox(
            "Do you have a primary care doctor?", ["Yes", "No"], index=0, key="pcp_access"
        )
    with col7:
        urgent_access = st.selectbox(
            "Can you get to urgent care today if needed?", ["Yes", "No"], index=0, key="urgent_access"
        )

    # Injury conditional section (defaults ensure variables exist even when not selected)
    injury_type = None
    injury_location = None
    injury_mechanism = None
    injury_flags: List[str] = []

    if chief == "Injury / wound":
        st.subheader("Injury / Wound Details")
        col8, col9 = st.columns(2)
        with col8:
            injury_type = st.selectbox(
                "What type of injury is this?", INJURY_TYPES, index=0, key="injury_type"
            )
            injury_location = st.selectbox(
                "Where is the injury?", INJURY_LOCATIONS, index=0, key="injury_location"
            )
        with col9:
            injury_mechanism = st.selectbox(
                "How did it happen?", INJURY_MECHANISMS, index=0, key="injury_mechanism"
            )
        injury_flags = st.multiselect("Are any of these present?", INJURY_FLAGS, key="injury_flags")

    st.divider()
    submitted = st.form_submit_button("Run Routing")


with st.expander("Run preset scenarios (sanity check)"):
    if st.button("Run all presets"):
        for name, preset in PRESETS.items():
            # Convert preset into the inputs dict route_patient expects
            inputs = {
                "age": int(preset["age"]),
                "sex": preset["sex"],
                "pregnant": preset["pregnant"],
                "chief_complaint": preset["chief_complaint"],
                "onset": preset["onset"],
                "severity_0_10": int(preset["severity_0_10"]),
                "trend": preset["trend"],
                "happened_before": preset["happened_before"],
                "fever": preset["fever"],
                "red_flags": preset.get("red_flags", []),
                "conditions": preset.get("conditions", []),
                "temp_f": parse_optional_float(preset.get("temp_f_raw", "")),
                "hr": parse_optional_int(preset.get("hr_raw", "")),
                "spo2": parse_optional_int(preset.get("spo2_raw", "")),
                "pcp_access": preset.get("pcp_access", "Yes"),
                "urgent_access": preset.get("urgent_access", "Yes"),
                "injury_type": preset.get("injury_type"),
                "injury_location": preset.get("injury_location"),
                "injury_mechanism": preset.get("injury_mechanism"),
                "injury_flags": preset.get("injury_flags", []),
     }
            res = route_patient(inputs)
            st.write(f"**{name}** → `{res.route}` ({res.urgency})")





if submitted:
    # -------------------------
    # Encounter metadata (new per submit)
    # -------------------------
    encounter_id = str(uuid.uuid4())[:8].upper()
    encounter_ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    # --- Ensure injury fields are always defined ---
    if chief == "Injury / wound":
        injury_type_out = injury_type
        injury_location_out = injury_location
        injury_mechanism_out = injury_mechanism
        injury_flags_out = injury_flags
    else:
        injury_type_out = None
        injury_location_out = None
        injury_mechanism_out = None
        injury_flags_out = []

    inputs = {
        "encounter_id": encounter_id,
        "encounter_ts": encounter_ts,
        "age": int(age),
        "sex": sex,
        "pregnant": pregnant,
        "chief_complaint": chief,
        "onset": onset,
        "severity_0_10": int(severity),
        "trend": trend,
        "happened_before": happened_before,
        "fever": fever,
        "red_flags": red_flags,
        "conditions": conditions,
        "temp_f": temp_f,
        "hr": hr,
        "spo2": spo2,
        "pcp_access": pcp_access,
        "urgent_access": urgent_access,
        "injury_type": injury_type_out,
        "injury_location": injury_location_out,
        "injury_mechanism": injury_mechanism_out,
        "injury_flags": injury_flags_out,
    }

    explanation = ""

    result = route_patient(inputs)

    st.subheader("Routing Result")
    st.caption(f"Encounter: **{encounter_id}** • **{encounter_ts}**")

    if result.route == "ED":
        st.error(f"Recommended care setting: **{result.route}**")
    elif result.route == "Urgent Care":
        st.warning(f"Recommended care setting: **{result.route}**")
    elif result.route == "PCP":
        st.info(f"Recommended care setting: **{result.route}**")
    else:
        st.success(f"Recommended care setting: **{result.route}**")

    st.write(f"**Urgency:** {result.urgency}")

    with st.expander("Why"):
        for r in result.reasons:
            st.markdown(f"- {r}")

    with st.expander("Safety notes"):
        for s in result.safety_notes:
            st.markdown(f"- {s}")

    # -------------------------
    # LLM Explanation 
    # -------------------------
    explanation = ""  # default for export when LLM disabled/unavailable

    with st.expander("LLM Explanation", expanded=True):
        if not llm_enabled():
            st.info("LLM is disabled. Set `OPENAI_API_KEY` in your environment to enable explanations.")
            explanation = ""
        else:
            prompt = build_explanation_prompt(inputs, result)
            explanation = generate_llm_explanation(prompt)
            st.write(explanation)


    # -------------------------
    # Export Summary
    # -------------------------
    st.subheader("Export Summary")

    # Patient export (handles old/new helper signature)
    try:
        patient_txt = format_patient_export(explanation, inputs) if explanation else ""
    except TypeError:
        patient_txt = format_patient_export(explanation) if explanation else ""

    clinician_txt = format_clinician_export(inputs, result)

    # --- Share Package Preview ---
    st.markdown("**Share package contents**")
    
    has_patient = bool(patient_txt.strip())
    has_clinician = bool(clinician_txt.strip())
    has_inputs = bool(inputs)
    
    preview_rows = [
        {"File": f"patient_summary_{encounter_id}.txt", "Included": "✅" if has_patient else "❌ (LLM off)"},
        {"File": f"clinician_summary_{encounter_id}.txt", "Included": "✅" if has_clinician else "❌"},
        {"File": f"inputs_{encounter_id}.json", "Included": "✅" if has_inputs else "❌"},
]

    st.table(preview_rows)


    # Build ZIP share package
    share_zip = build_share_package_zip(
        encounter_id=encounter_id,
        patient_txt=patient_txt,
        clinician_txt=clinician_txt,
        inputs=inputs,
    )

    st.download_button(
        label="Download Share Package (.zip)",
        data=share_zip,
        file_name=f"share_package_{encounter_id}.zip",
        mime="application/zip",
    )

    colA, colB = st.columns(2)

    with colA:
        st.markdown("**Patient summary**")
        if patient_txt:
            st.download_button(
                label="Download patient summary (.txt)",
                data=patient_txt,
                file_name=f"patient_summary_{encounter_id}.txt",
                mime="text/plain",
            )
            st.code(patient_txt, language="text")
        else:
            st.info("No patient summary yet (LLM disabled or unavailable).")

    with colB:
        st.markdown("**Clinician summary**")
        st.download_button(
            label="Download clinician summary (.txt)",
            data=clinician_txt,
            file_name=f"clinician_summary_{encounter_id}.txt",
            mime="text/plain",
        )
        st.code(clinician_txt, language="text")

    st.caption("Tip: on mobile, press-and-hold text in the boxes to copy, or download the .txt.")

    with st.expander("Debug: inputs JSON"):
        st.json(inputs)
