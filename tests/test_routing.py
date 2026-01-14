# tests/test_routing.py
from triage.routing import route_patient

def test_low_spo2_goes_to_ed():
    res = route_patient({
        "chief_complaint": "Shortness of breath",
        "severity_0_10": 5,
        "trend": "Worse",
        "happened_before": "Not sure",
        "fever": "No",
        "red_flags": [],
        "conditions": [],
        "spo2": 89,
        "pcp_access": "Yes",
        "injury_flags": [],
        "pregnant": "Not applicable",
    })
    assert res.route == "ED"

def test_pregnancy_plus_fever_goes_to_urgent():
    res = route_patient({
        "chief_complaint": "Fever / infection symptoms",
        "severity_0_10": 4,
        "trend": "Same",
        "happened_before": "Not sure",
        "fever": "Yes",
        "red_flags": [],
        "conditions": [],
        "spo2": None,
        "pcp_access": "Yes",
        "injury_flags": [],
        "pregnant": "Yes",
    })
    assert res.route == "Urgent Care"

def test_no_pcp_moderate_symptoms_routes_to_urgent():
    res = route_patient({
        "chief_complaint": "Abdominal pain",
        "severity_0_10": 5,
        "trend": "Worse",
        "happened_before": "Not sure",
        "fever": "No",
        "red_flags": [],
        "conditions": [],
        "spo2": None,
        "pcp_access": "No",
        "injury_flags": [],
        "pregnant": "Not applicable",
    })
    assert res.route == "Urgent Care"

def test_uncontrolled_bleeding_routes_to_ed():
    res = route_patient({
        "chief_complaint": "Injury / wound",
        "severity_0_10": 5,
        "trend": "Same",
        "happened_before": "No — first time",
        "fever": "No",
        "red_flags": [],  # keep empty to test injury flag path
        "conditions": [],
        "spo2": None,
        "pcp_access": "No",
        "injury_flags": ["Bleeding that won’t stop after 10 minutes of firm pressure"],
        "pregnant": "Not applicable",
    })
    assert res.route == "ED"

def test_red_flag_chest_pain_goes_to_ed():
    res = route_patient({
        "chief_complaint": "Chest pain / pressure",
        "severity_0_10": 8,
        "trend": "Worse",
        "happened_before": "No — first time",
        "fever": "No",
        "red_flags": ["Severe chest pain/pressure"],
        "conditions": ["Heart disease / prior heart attack"],
        "spo2": None,
        "pcp_access": "Yes",
        "injury_flags": [],
        "pregnant": "Not applicable",
    })
    assert res.route == "ED"

def test_fever_immunocompromised_goes_to_urgent():
    res = route_patient({
        "chief_complaint": "Fever / infection symptoms",
        "severity_0_10": 6,
        "trend": "Worse",
        "happened_before": "Not sure",
        "fever": "Yes",
        "red_flags": [],
        "conditions": ["Immunocompromised (chemo, transplant, HIV, long-term steroids)"],
        "spo2": 96,
        "pcp_access": "Yes",
        "injury_flags": [],
        "pregnant": "No",
    })
    assert res.route == "Urgent Care"

def test_mild_stable_recurrent_routes_to_pcp_when_access():
    res = route_patient({
        "chief_complaint": "Cough / sore throat",
        "severity_0_10": 2,
        "trend": "Same",
        "happened_before": "Yes — similar symptoms before",
        "fever": "Don’t know / can’t check",
        "red_flags": [],
        "conditions": [],
        "spo2": None,
        "pcp_access": "Yes",
        "injury_flags": [],
        "pregnant": "Not applicable",
    })
    assert res.route == "PCP"

def test_injury_cant_bear_weight_goes_to_urgent():
    res = route_patient({
        "chief_complaint": "Injury / wound",
        "severity_0_10": 6,
        "trend": "Worse",
        "happened_before": "No — first time",
        "fever": "No",
        "red_flags": [],
        "conditions": [],
        "spo2": None,
        "pcp_access": "No",
        "injury_flags": ["Unable to bear weight or use limb"],
        "pregnant": "Not applicable",
    })
    assert res.route == "Urgent Care"
