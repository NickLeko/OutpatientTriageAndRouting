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
# Data Models
# -----------------------------
@dataclass
class RoutingResult:
    route: str                 # "ED" | "Urgent Care" | "PCP" | "Self-care"
    urgency: str               # "Immediate" | "Same day" | "24–72 hrs" | "Monitor"
    reasons: List[str]         # machine-readable justifications (not LLM)
    safety_notes: List[str]    # watch-outs / escalation triggers


# -----------------------------
# Helpers
# -----------------------------
def _is_checked(items: List[str]) -> bool:
    return bool(items) and len(items) > 0

def apply_preset(preset: Dict) -> None:
    """
    Write preset values into Streamlit session_state so widgets update.
    IMPORTANT: keys must match widget `key=` values.
    """
    for k, v in preset.items():
        st.session_state[k] = v


def normalize_conditions(conditions: List[str]) -> List[str]:
    # If "None of the above" selected, treat as no conditions.
    if "None of the above" in conditions:
        return []
    return conditions


def parse_optional_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


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
# Routing Logic 
# -----------------------------
def route_patient(inputs: Dict) -> RoutingResult:
    """
    Deterministic triage routing v1.
    Order matters. First match wins.
    """
    reasons: List[str] = []
    safety: List[str] = [
        "If symptoms rapidly worsen, seek urgent evaluation.",
        "If you develop new red-flag symptoms (trouble breathing, fainting, severe chest pain, stroke signs), go to the ED.",
    ]

    chief = inputs.get("chief_complaint")
    severity = int(inputs.get("severity_0_10", 0))
    trend = inputs.get("trend")
    fever = inputs.get("fever")
    happened_before = inputs.get("happened_before")
    pregnant = inputs.get("pregnant")
    conditions = normalize_conditions(inputs.get("conditions", []))
    red_flags = inputs.get("red_flags", [])
    injury_flags = inputs.get("injury_flags", [])
    injury_type = inputs.get("injury_type")
    spo2 = inputs.get("spo2")  # Optional numeric
    pcp_access = inputs.get("pcp_access")
    urgent_access = inputs.get("urgent_access")

    # ---- STEP 1: Immediate ED hard stops (global red flags)
    if _is_checked(red_flags):
        reasons.append("One or more red-flag symptoms selected.")
        # Tighten: if uncontrolled bleeding in either global or injury flags, be explicit.
        if "Uncontrolled bleeding" in red_flags or "Bleeding that won’t stop after 10 minutes of firm pressure" in injury_flags:
            reasons.append("Uncontrolled bleeding criteria met.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # Optional vitals hard stop: low oxygen saturation if provided
    if spo2 is not None and spo2 < 92:
        reasons.append(f"Low oxygen saturation provided (SpO₂={spo2}%).")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # ---- STEP 2: Injury-specific escalation
    if chief == "Injury / wound":
        # ED injury criteria
        ed_injury = any(
            flag in injury_flags
            for flag in [
                "Obvious deformity",
                "Bone visible or deep open wound",
                "Bleeding that won’t stop after 10 minutes of firm pressure",
                "Numbness or tingling",
            ]
        )
        if ed_injury:
            reasons.append("Injury criteria suggests emergent evaluation (deformity/open wound/uncontrolled bleeding/neuro symptoms).")
            return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

        # Urgent Care injury criteria
        uc_injury = any(
            flag in injury_flags
            for flag in [
                "Unable to bear weight or use limb",
                "Severe swelling",
            ]
        ) or severity >= 6

        if uc_injury:
            reasons.append("Injury criteria suggests same-day evaluation (can’t bear weight/severe swelling/high pain).")
            return RoutingResult(route="Urgent Care", urgency="Same day", reasons=reasons, safety_notes=safety)

        # Otherwise, mild injury
        reasons.append("No injury red flags; symptoms appear mild/stable by provided inputs.")
        return RoutingResult(route="Self-care", urgency="Monitor", reasons=reasons, safety_notes=safety)

    # ---- STEP 3: High-risk combos (conservative)
    has_heart = "Heart disease / prior heart attack" in conditions
    has_lung = "Chronic lung disease (asthma/COPD)" in conditions
    immunocompromised = "Immunocompromised (chemo, transplant, HIV, long-term steroids)" in conditions

    # Chest pain + heart history
    if chief == "Chest pain / pressure" and has_heart:
        reasons.append("Chest pain/pressure with cardiac history.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # SOB + lung disease + worsening
    if chief == "Shortness of breath" and has_lung and trend == "Worse":
        reasons.append("Shortness of breath with chronic lung disease and worsening trend.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # Severe headache + first occurrence
    if chief == "Headache" and severity >= 7 and happened_before.startswith("No"):
        reasons.append("Severe headache (≥7/10) and first-time occurrence.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # Fever + immunocompromised (at least urgent; consider ED if severe)
    if fever == "Yes" and immunocompromised and severity >= 7:
        reasons.append("Fever in immunocompromised patient with high severity.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # ---- STEP 4: Urgent Care (same day)
    urgent_triggers: List[str] = []
    if severity >= 6:
        urgent_triggers.append("Severity ≥6/10.")
    if trend == "Worse":
        urgent_triggers.append("Symptoms worsening.")
    if fever == "Yes" and immunocompromised:
        urgent_triggers.append("Fever with immunocompromised status.")
    if happened_before.startswith("No") and severity >= 5:
        urgent_triggers.append("First-time symptoms with moderate severity (≥5/10).")
    if pregnant == "Yes" and fever == "Yes":
        urgent_triggers.append("Pregnancy + fever (needs clinician evaluation).")
    if pcp_access == "No" and (severity >= 5 or fever == "Yes" or trend == "Worse"):
        urgent_triggers.append("No PCP access with symptoms likely needing in-person assessment.")

    if urgent_triggers:
        reasons.extend(urgent_triggers)
        return RoutingResult(route="Urgent Care", urgency="Same day", reasons=reasons, safety_notes=safety)

    # ---- STEP 5: Primary Care (24–72 hrs)
    pcp_triggers: List[str] = []
    stable = trend in ("Same", "Better")

    if stable and (3 <= severity <= 5):
        pcp_triggers.append("Stable symptoms with mild–moderate severity (3–5/10).")
    if happened_before.startswith("Yes") and stable:
        pcp_triggers.append("Recurrent similar symptoms with stable trend.")
    if fever == "Yes" and stable and severity <= 5:
        pcp_triggers.append("Fever present but no red flags and overall stable by inputs.")

    if pcp_triggers and pcp_access == "Yes":
        reasons.extend(pcp_triggers)
        return RoutingResult(route="PCP", urgency="24–72 hrs", reasons=reasons, safety_notes=safety)

    # If PCP triggers exist but no PCP access, send to urgent care.
    if pcp_triggers and pcp_access == "No":
        reasons.extend(pcp_triggers)
        reasons.append("No PCP access; recommending urgent care instead.")
        return RoutingResult(route="Urgent Care", urgency="Same day", reasons=reasons, safety_notes=safety)

    # ---- STEP 6: Self-care / monitor
    reasons.append("No red flags or escalation criteria met based on provided inputs.")
    return RoutingResult(route="Self-care", urgency="Monitor", reasons=reasons, safety_notes=safety)


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

    result = route_patient(inputs)

    st.subheader("Routing Result")
    if result.route == "ED":
        st.error(f"Recommended care setting: **{result.route}**")
    elif result.route == "Urgent Care":
        st.warning(f"Recommended care setting: **{result.route}**")
    elif result.route == "PCP":
        st.info(f"Recommended care setting: **{result.route}**")
    else:
        st.success(f"Recommended care setting: **{result.route}**")

    st.write(f"**Urgency:** {result.urgency}")

    with st.expander("Why (rules-based)"):
        for r in result.reasons:
            st.markdown(f"- {r}")

    with st.expander("Safety notes"):
        for s in result.safety_notes:
            st.markdown(f"- {s}")

    with st.expander("LLM Explanation (optional)", expanded=True):
        if not llm_enabled():
            st.info("LLM is disabled. Set `OPENAI_API_KEY` in your environment to enable explanations.")
        else:
            prompt = build_explanation_prompt(inputs, result)
            explanation = generate_llm_explanation(prompt)
            st.write(explanation)

    with st.expander("Debug: inputs JSON"):
        st.json(inputs)

st.caption("Next: add export/share functionality (PDF or text) or harden tests.")
