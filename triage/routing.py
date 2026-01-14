# triage/routing.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class RoutingResult:
    route: str
    urgency: str
    reasons: List[str]
    safety_notes: List[str]


def _is_checked(items: List[str]) -> bool:
    return bool(items) and len(items) > 0


def normalize_conditions(conditions: List[str]) -> List[str]:
    if "None of the above" in conditions:
        return []
    return conditions


def route_patient(inputs: Dict[str, Any]) -> RoutingResult:
    reasons: List[str] = []
    safety: List[str] = [
        "If symptoms rapidly worsen, seek urgent evaluation.",
        "If you develop new red-flag symptoms (trouble breathing, fainting, severe chest pain, stroke signs), go to the ED.",
    ]

    chief = inputs.get("chief_complaint")
    severity = int(inputs.get("severity_0_10", 0))
    trend = inputs.get("trend")
    fever = inputs.get("fever")
    happened_before = inputs.get("happened_before", "")
    pregnant = inputs.get("pregnant")
    conditions = normalize_conditions(inputs.get("conditions", []))
    red_flags = inputs.get("red_flags", [])
    injury_flags = inputs.get("injury_flags", [])
    spo2 = inputs.get("spo2")  # Optional numeric
    pcp_access = inputs.get("pcp_access")

    # STEP 1: Immediate ED hard stops (global red flags)
    if _is_checked(red_flags):
        reasons.append("One or more red-flag symptoms selected.")
        if "Uncontrolled bleeding" in red_flags or "Bleeding that won’t stop after 10 minutes of firm pressure" in injury_flags:
            reasons.append("Uncontrolled bleeding criteria met.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # Optional vitals hard stop
    if spo2 is not None:
        try:
            if int(spo2) < 92:
                reasons.append(f"Low oxygen saturation provided (SpO₂={spo2}%).")
                return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)
        except Exception:
            pass

    # STEP 2: Injury-specific escalation
    if chief == "Injury / wound":
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

        reasons.append("No injury red flags; symptoms appear mild/stable by provided inputs.")
        return RoutingResult(route="Self-care", urgency="Monitor", reasons=reasons, safety_notes=safety)

    # STEP 3: High-risk combos
    has_heart = "Heart disease / prior heart attack" in conditions
    has_lung = "Chronic lung disease (asthma/COPD)" in conditions
    immunocompromised = "Immunocompromised (chemo, transplant, HIV, long-term steroids)" in conditions

    if chief == "Chest pain / pressure" and has_heart:
        reasons.append("Chest pain/pressure with cardiac history.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    if chief == "Shortness of breath" and has_lung and trend == "Worse":
        reasons.append("Shortness of breath with chronic lung disease and worsening trend.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    if chief == "Headache" and severity >= 7 and happened_before.startswith("No"):
        reasons.append("Severe headache (≥7/10) and first-time occurrence.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    if fever == "Yes" and immunocompromised and severity >= 7:
        reasons.append("Fever in immunocompromised patient with high severity.")
        return RoutingResult(route="ED", urgency="Immediate", reasons=reasons, safety_notes=safety)

    # STEP 4: Urgent Care
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

    # STEP 5: Primary Care
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

    if pcp_triggers and pcp_access == "No":
        reasons.extend(pcp_triggers)
        reasons.append("No PCP access; recommending urgent care instead.")
        return RoutingResult(route="Urgent Care", urgency="Same day", reasons=reasons, safety_notes=safety)

    # STEP 6: Self-care
    reasons.append("No red flags or escalation criteria met based on provided inputs.")
    return RoutingResult(route="Self-care", urgency="Monitor", reasons=reasons, safety_notes=safety)
