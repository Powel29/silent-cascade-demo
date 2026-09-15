"""Decision Firewall policy tests (CLAUDE.md section 19)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from conftest import make_graph
from cascade import criticality_ranking
from decision_firewall import (
    advance_acknowledgement,
    assess_risk,
    build_action_plan,
    build_asset_context,
    classify_for_firewall,
    detect_safety_hazards,
    reliability_state_from_canary,
    run_firewall,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def cfg() -> dict:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def complaints() -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / "data" / "complaints.csv").set_index("id")


@pytest.fixture(scope="module")
def small_world():
    """Tiny graph + full ranking so asset context can be built without the real pickle."""
    # A-B-C chain cascades fully from any end; Z is an isolated, well-provisioned substation
    # whose failure affects only itself -> the least critical (normal-tier) asset.
    G = make_graph(
        subs={"A": (120, 100, 1000), "B": (120, 80, 2000), "C": (120, 90, 3000), "D": (500, 50, 500), "Z": (500, 50, 100)},
        grid=[("A", "B"), ("B", "C"), ("C", "D")],
        hospitals={"H1": ("A", 8.0)},
        pumps={"P1": ("B", 6.0)},
    )
    rank = criticality_ranking(G, top_n=None)
    return G, rank


def _ctx(small_world, cfg, asset):
    G, rank = small_world
    return build_asset_context(G, asset, rank, cfg)


def _base_input(**over) -> dict:
    base = {
        "complaint_id": "x", "original_text": "The streetlight on our lane has been flickering.", "language": "en",
        "structured_hazards": [], "immediate_danger": False, "predicted_dept": "electrical_maintenance",
        "prediction_margin": 2, "classifier_input_complete": True, "asset_id": None,
        "asset_criticality_percentile": None, "simulated_people_exposed": None, "dependent_hospitals": None,
        "dependent_water_assets": None, "proposed_sla_hours": 336.0, "scenario_failure_window_hours": None,
        "reliability_state": "normal",
    }
    base.update(over)
    return base


def _scan(text="nothing hazardous here", language="en", structured=None, immediate=False, cfg=None):
    return detect_safety_hazards(text, language, structured, immediate, cfg["firewall"] if cfg else None)


# ------------------------------------------------------------------ safety scan


def test_scan_reads_complete_original_text_not_truncated_input(complaints, cfg):
    text = complaints.loc["c01", "text_native"]
    clf = classify_for_firewall(text, "truncated", cfg)
    assert clf["input_complete"] is False
    assert clf["predicted_dept"] == ""  # the truncated classifier cannot parse it ...
    scan = _scan(text, "native", cfg=cfg)
    assert "electrical_sparking" in scan["hazards"]  # ... but the original text still carries the hazard
    assert scan["direct_hazard"] is True
    assert all(m["source"] == "original_text" for m in scan["matched_terms"])
    assert scan["scanned_text_length"] == len(text) > cfg["d2"]["truncate_chars"]


def test_scan_is_independent_of_department_prediction(complaints, cfg):
    text = complaints.loc["c03", "text_en"]
    a = _scan(text, "en", cfg=cfg)
    # the scan takes no prediction at all; the same text always yields the same hazards
    assert a == _scan(text, "en", cfg=cfg)
    assert "live_wire" in a["hazards"]


def test_structured_intake_provides_signal_without_text(cfg):
    scan = _scan("", "native", structured=["sparks"], immediate=True, cfg=cfg)
    assert "electrical_sparking" in scan["hazards"]
    assert scan["immediate_danger"] is True
    assert {m["source"] for m in scan["matched_terms"]} == {"structured_intake"}


def test_service_hazard_is_not_a_direct_hazard(complaints, cfg):
    scan = _scan(complaints.loc["c06", "text_en"], "en", cfg=cfg)
    assert scan["hazards"] == ["burst_pipe"]
    assert scan["direct_hazard"] is False
    assert scan["service_hazards"] == ["burst_pipe"]


# ------------------------------------------------------------------ policy


def test_structured_immediate_danger_always_red(cfg):
    scan = _scan("", "en", immediate=True, cfg=cfg)
    for rel in ("normal", "degraded", "unavailable"):
        d = assess_risk(_base_input(reliability_state=rel, immediate_danger=True), scan, {}, cfg["firewall"], cfg)
        assert d["risk_level"] == "red"
        assert "STRUCTURED_IMMEDIATE_DANGER" in d["reason_codes"]
        assert d["dispatch_immediate"] and d["human_review_required"] and not d["ai_autonomy_allowed"]


def test_electrical_hazard_plus_non_emergency_prediction_is_red(complaints, cfg):
    scan = _scan(complaints.loc["c20", "text_en"], "en", cfg=cfg)
    d = assess_risk(_base_input(predicted_dept="electrical_maintenance"), scan, {}, cfg["firewall"], cfg)
    assert d["risk_level"] == "red"
    assert {"DIRECT_HAZARD", "DANGEROUS_DOWNGRADE"} <= set(d["reason_codes"])
    assert d["final_department"] == "electrical_emergency"
    assert d["ai_route_overridden"] is True


def test_direct_hazard_with_correct_emergency_prediction_is_still_red_but_not_a_downgrade(complaints, cfg):
    scan = _scan(complaints.loc["c13", "text_en"], "en", cfg=cfg)
    d = assess_risk(_base_input(predicted_dept="electrical_emergency", proposed_sla_hours=4.0), scan, {}, cfg["firewall"], cfg)
    assert d["risk_level"] == "red"
    assert "DANGEROUS_DOWNGRADE" not in d["reason_codes"]
    assert d["ai_route_overridden"] is False


def test_unparseable_without_danger_is_at_least_yellow(cfg):
    d = assess_risk(_base_input(predicted_dept="", prediction_margin=0, proposed_sla_hours=336.0), _scan(cfg=cfg), {}, cfg["firewall"], cfg)
    assert d["risk_level"] in ("yellow", "red")
    assert "UNPARSEABLE_CLASSIFICATION" in d["reason_codes"]
    assert d["ai_autonomy_allowed"] is False


@pytest.mark.parametrize("rel", ["degraded", "unavailable"])
def test_degraded_or_unavailable_reliability_prevents_green(cfg, small_world, rel):
    ctx = _ctx(small_world, cfg, "Z")  # least critical asset
    d = assess_risk(_base_input(reliability_state=rel, asset_id="D"), _scan(cfg=cfg), ctx, cfg["firewall"], cfg)
    assert d["risk_level"] == "yellow"
    assert ("RELIABILITY_DEGRADED" if rel == "degraded" else "RELIABILITY_UNAVAILABLE") in d["reason_codes"]


def test_degraded_reliability_plus_direct_hazard_is_red(complaints, cfg):
    scan = _scan(complaints.loc["c01", "text_native"], "native", cfg=cfg)
    d = assess_risk(_base_input(reliability_state="degraded"), scan, {}, cfg["firewall"], cfg)
    assert d["risk_level"] == "red"
    assert "RELIABILITY_DEGRADED" in d["reason_codes"]


def test_missing_required_asset_context_prevents_green(cfg):
    unavailable = build_asset_context(None, None, None, cfg)
    assert unavailable["context_available"] is False
    d = assess_risk(_base_input(), _scan(cfg=cfg), unavailable, cfg["firewall"], cfg)
    assert d["risk_level"] == "yellow"
    assert "ASSET_CONTEXT_MISSING" in d["reason_codes"]
    assert "asset_context" in d["missing_fields"]


def test_asset_context_not_required_for_non_infrastructure_departments(cfg):
    d = assess_risk(_base_input(predicted_dept="sanitation", proposed_sla_hours=72.0), _scan(cfg=cfg), build_asset_context(None, None, None, cfg), cfg["firewall"], cfg)
    assert d["risk_level"] == "green"


def test_clean_low_risk_complaint_can_be_green(cfg, small_world):
    ctx = _ctx(small_world, cfg, "Z")
    assert ctx["criticality_tier"] == "normal"
    d = assess_risk(_base_input(asset_id="Z"), _scan(cfg=cfg), ctx, cfg["firewall"], cfg)
    assert d["risk_level"] == "green"
    assert d["reason_codes"] == ["SAFE_AUTOMATION_ALLOWED"]
    assert d["ai_autonomy_allowed"] and not d["human_review_required"] and not d["dispatch_immediate"]


def test_asset_criticality_changes_the_decision(cfg, small_world):
    normal = _ctx(small_world, cfg, "Z")
    top = _ctx(small_world, cfg, "D")
    assert top["criticality_tier"] == "very_high"
    scan = _scan(cfg=cfg)
    assert assess_risk(_base_input(asset_id="Z"), scan, normal, cfg["firewall"], cfg)["risk_level"] == "green"
    d = assess_risk(_base_input(asset_id="D"), scan, top, cfg["firewall"], cfg)
    assert d["risk_level"] == "yellow"
    assert "VERY_HIGH_ASSET_CRITICALITY" in d["reason_codes"]
    # direct hazard on a very-high asset -> Red with the criticality reason attached
    hazard = _scan("sparks from the transformer", "en", cfg=cfg)
    d2 = assess_risk(_base_input(asset_id="D"), hazard, top, cfg["firewall"], cfg)
    assert d2["risk_level"] == "red" and "VERY_HIGH_ASSET_CRITICALITY" in d2["reason_codes"]


def test_repair_window_rule(cfg, small_world):
    top = _ctx(small_world, cfg, "D")
    d = assess_risk(_base_input(asset_id="D", proposed_sla_hours=336.0, scenario_failure_window_hours=336.0), _scan(cfg=cfg), top, cfg["firewall"], cfg)
    assert d["risk_level"] == "red" and "REPAIR_WINDOW_AT_RISK" in d["reason_codes"]
    normal = _ctx(small_world, cfg, "Z")
    d2 = assess_risk(_base_input(asset_id="Z", proposed_sla_hours=336.0, scenario_failure_window_hours=336.0), _scan(cfg=cfg), normal, cfg["firewall"], cfg)
    assert d2["risk_level"] == "yellow" and "REPAIR_WINDOW_AT_RISK" in d2["reason_codes"]


def test_low_margin_and_truncation_are_yellow(cfg):
    d = assess_risk(_base_input(predicted_dept="sanitation", proposed_sla_hours=72.0, prediction_margin=0), _scan(cfg=cfg), {}, cfg["firewall"], cfg)
    assert d["risk_level"] == "yellow" and "LOW_MARGIN" in d["reason_codes"]
    d = assess_risk(_base_input(predicted_dept="sanitation", proposed_sla_hours=72.0, classifier_input_complete=False), _scan(cfg=cfg), {}, cfg["firewall"], cfg)
    assert d["risk_level"] == "yellow" and "TRUNCATED_CLASSIFIER_INPUT" in d["reason_codes"]


def test_conflicting_service_hazard_and_department(complaints, cfg):
    scan = _scan(complaints.loc["c06", "text_en"], "en", cfg=cfg)  # burst pipe
    ok = assess_risk(_base_input(predicted_dept="water_supply", proposed_sla_hours=72.0), scan, {}, cfg["firewall"], cfg)
    assert ok["risk_level"] == "green"
    bad = assess_risk(_base_input(predicted_dept="roads", proposed_sla_hours=336.0), scan, {}, cfg["firewall"], cfg)
    assert bad["risk_level"] == "yellow" and "CONFLICTING_SIGNALS" in bad["reason_codes"]


def test_reason_text_matches_codes(cfg):
    scan = _scan("sparks and fire", "en", cfg=cfg)
    d = assess_risk(_base_input(), scan, {}, cfg["firewall"], cfg)
    assert len(d["reason_codes"]) == len(d["reason_text"])
    assert len(set(d["reason_codes"])) == len(d["reason_codes"])
    assert all(isinstance(t, str) and t for t in d["reason_text"])


def test_runtime_policy_refuses_ground_truth(cfg):
    with pytest.raises(ValueError):
        assess_risk(_base_input(true_dept="electrical_emergency"), _scan(cfg=cfg), {}, cfg["firewall"], cfg)


def test_run_firewall_trace_has_no_ground_truth(complaints, cfg):
    trace = run_firewall("c01", complaints.loc["c01", "text_native"], "native", "truncated", cfg)
    assert "true_dept" not in trace["firewall_input"]
    assert "true_dept" not in trace["decision"]["signals"]
    assert trace["decision"]["risk_level"] == "red"


# ------------------------------------------------------------------ asset context


def test_asset_context_validates_and_never_defaults_to_most_critical(cfg, small_world):
    G, rank = small_world
    missing = build_asset_context(G, "nope", rank, cfg)
    assert missing["context_available"] is False and missing["criticality_tier"] == "unknown"
    assert build_asset_context(G, "H1", rank, cfg)["context_available"] is False  # not a substation
    assert build_asset_context(G, None, rank, cfg)["context_available"] is False
    good = build_asset_context(G, "D", rank, cfg)
    assert good["context_available"] and good["criticality_rank"] == 1 and good["n_ranked_assets"] == 5
    assert build_asset_context(G, "A", rank, cfg)["criticality_rank"] == 2
    assert good["provenance"]["asset_mapping"].startswith("synthetic")


# ------------------------------------------------------------------ reliability


def test_reliability_state_from_canary(cfg):
    rep = pd.DataFrame([
        {"condition": "clean", "language": "en", "accuracy_pct": 100, "unparseable_pct": 0},
        {"condition": "clean", "language": "native", "accuracy_pct": 100, "unparseable_pct": 0},
        {"condition": "truncated", "language": "en", "accuracy_pct": 90, "unparseable_pct": 10},
        {"condition": "truncated", "language": "native", "accuracy_pct": 55, "unparseable_pct": 45},
    ])
    assert reliability_state_from_canary(None, "native", "clean", cfg) == "unavailable"
    assert reliability_state_from_canary(rep, "native", "clean", cfg) == "normal"
    assert reliability_state_from_canary(rep, "en", "truncated", cfg) == "normal"
    assert reliability_state_from_canary(rep, "native", "truncated", cfg) == "degraded"
    assert reliability_state_from_canary(rep, "native", "small_model", cfg) == "unavailable"


# ------------------------------------------------------------------ action plan


def test_red_creates_immediate_dispatch_plus_parallel_review(cfg):
    d = assess_risk(_base_input(), _scan("sparks", "en", cfg=cfg), {}, cfg["firewall"], cfg)
    plan = build_action_plan(d, "electrical_maintenance", cfg["firewall"])
    assert plan["work_order_type"] == "emergency_work_order"
    assert plan["assigned_department"] == "electrical_emergency"
    assert plan["human_review_parallel"] is True and plan["requires_acknowledgement"] is True
    assert plan["status"] == "dispatched_awaiting_acknowledgement"
    assert plan["simulated"] is True and plan["ai_route_finalized"] is False


def test_yellow_does_not_finalize_automatic_route(cfg):
    d = assess_risk(_base_input(predicted_dept="", prediction_margin=0), _scan(cfg=cfg), {}, cfg["firewall"], cfg)
    plan = build_action_plan(d, "", cfg["firewall"])
    assert plan["work_order_type"] == "human_verification_task"
    assert plan["ai_route_finalized"] is False
    assert plan["assigned_department"] == "verification_desk"


def test_green_creates_normal_routed_ticket(cfg):
    d = assess_risk(_base_input(predicted_dept="sanitation", proposed_sla_hours=72.0), _scan(cfg=cfg), {}, cfg["firewall"], cfg)
    plan = build_action_plan(d, "sanitation", cfg["firewall"])
    assert plan["work_order_type"] == "routed_ticket" and plan["ai_route_finalized"] is True
    assert plan["requires_acknowledgement"] is False


def test_unacknowledged_red_reescalates(cfg):
    d = assess_risk(_base_input(), _scan("sparks", "en", cfg=cfg), {}, cfg["firewall"], cfg)
    plan = build_action_plan(d, "electrical_maintenance", cfg["firewall"])
    target = cfg["firewall"]["action_policy"]["red_reescalation_target_minutes"]
    waiting = advance_acknowledgement(plan, acknowledged=False, minutes_elapsed=target - 1, policy=cfg["firewall"])
    assert waiting["acknowledgement_state"] == "awaiting"
    late = advance_acknowledgement(plan, acknowledged=False, minutes_elapsed=target, policy=cfg["firewall"])
    assert late["acknowledgement_state"] == "reescalated"
    assert late["status"].startswith("reescalated_to_")
    ok = advance_acknowledgement(plan, acknowledged=True, minutes_elapsed=5, policy=cfg["firewall"])
    assert ok["status"] == "acknowledged"
    assert plan["status"] == "dispatched_awaiting_acknowledgement"  # input plan not mutated


def test_three_levels_produce_materially_different_actions(cfg, small_world):
    ctx = _ctx(small_world, cfg, "Z")
    green = build_action_plan(assess_risk(_base_input(asset_id="Z"), _scan(cfg=cfg), ctx, cfg["firewall"], cfg), "electrical_maintenance", cfg["firewall"])
    yellow = build_action_plan(assess_risk(_base_input(asset_id="Z", prediction_margin=0), _scan(cfg=cfg), ctx, cfg["firewall"], cfg), "electrical_maintenance", cfg["firewall"])
    red = build_action_plan(assess_risk(_base_input(asset_id="Z"), _scan("fire", "en", cfg=cfg), ctx, cfg["firewall"], cfg), "electrical_maintenance", cfg["firewall"])
    assert len({green["work_order_type"], yellow["work_order_type"], red["work_order_type"]}) == 3
    assert len({green["status"], yellow["status"], red["status"]}) == 3


def test_yellow_response_time_does_not_assume_an_emergency_upgrade(cfg, small_world, complaints):
    """Regression: a Yellow with no hazard must not be costed as if the verifier reroutes the
    case to the 4 h emergency queue. Assuming that understates the response time and can make
    the app claim a failure was prevented when it would not be."""
    ctx = _ctx(small_world, cfg, "Z")
    review = float(cfg["firewall"]["action_policy"]["yellow_review_target_hours"])
    maint = float(cfg["d2"]["sla_hours"]["electrical_maintenance"])
    trace = run_firewall("c02", complaints.loc["c02", "text_native"], "native", "clean", cfg,
                         asset_context=ctx, reliability_state="normal", scenario_failure_window_hours=maint)
    assert trace["decision"]["risk_level"] == "yellow"
    assert trace["decision"]["recommended_department"] == "electrical_maintenance"
    # review target + the route a verifier would actually confirm, not review target + 4 h
    assert trace["response_hours"] == review + maint
    assert trace["response_hours"] >= maint  # so the failure window is NOT beaten
    # a Red case still gets the emergency response time
    red = run_firewall("c01", complaints.loc["c01", "text_native"], "native", "truncated", cfg,
                       asset_context=ctx, reliability_state="normal", scenario_failure_window_hours=maint)
    assert red["decision"]["risk_level"] == "red"
    assert red["response_hours"] == float(cfg["firewall"]["emergency_response_hours"])


def test_yellow_response_follows_a_detected_service_hazard(cfg, small_world, complaints):
    """When the scan finds a service hazard that contradicts the AI department, the verifier is
    assumed to correct to the hazard's department — still runtime evidence, never ground truth."""
    ctx = _ctx(small_world, cfg, "Z")
    review = float(cfg["firewall"]["action_policy"]["yellow_review_target_hours"])
    trace = run_firewall("c17", complaints.loc["c17", "text_native"], "native", "clean", cfg,
                         asset_context=ctx, reliability_state="normal")
    d = trace["decision"]
    assert d["risk_level"] == "yellow" and "CONFLICTING_SIGNALS" in d["reason_codes"]
    assert trace["response_hours"] == review + float(cfg["d2"]["sla_hours"]["water_supply"])
