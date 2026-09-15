"""Comparative evaluation tests (CLAUDE.md section 19, evaluation)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

import decision_firewall
from evaluate_firewall import (
    CONFIGURATIONS,
    aggregate,
    build_decision_trace,
    evaluate_cases,
    load_complaints,
    load_config,
    load_full_ranking,
    load_graph,
    load_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
NEEDS_OUTPUTS = pytest.mark.skipif(
    not (REPO_ROOT / "outputs" / "d1_criticality.csv").exists() or not (REPO_ROOT / "data" / "processed" / "graph.gpickle").exists(),
    reason="requires the built graph and the full D1 ranking (python src/build_graph.py && python src/d1_cascade.py)",
)


@pytest.fixture(scope="module")
def world():
    cfg = load_config()
    complaints = load_complaints()
    graph = load_graph()
    ranking = load_full_ranking()
    scenarios = load_scenarios(complaints, graph)
    return cfg, complaints, graph, ranking, scenarios


@pytest.fixture(scope="module")
def decisions(world):
    cfg, complaints, graph, ranking, scenarios = world
    return evaluate_cases(complaints, scenarios, graph, ranking, cfg)


@NEEDS_OUTPUTS
def test_matrix_and_denominators(decisions):
    ev = aggregate(decisions).set_index("configuration")
    for config in CONFIGURATIONS:
        row = ev.loc[config]
        assert row.n_cases == 120  # 20 complaints x 2 languages x 3 conditions
        assert row.n_critical_cases == 24  # 4 electrical_emergency complaints x 6
        assert row.n_noncritical_ai_correct + row.n_noncritical_ai_wrong == 96
        assert row.dangerous_misroutes_allowed + row.dangerous_misroutes_intercepted == row.n_dangerous_ai_routes
        assert row.safe_automation_count + row.unnecessary_escalations <= row.n_noncritical_ai_correct
        assert 0 <= row.human_review_rate <= 1
    # AI correctness and the dangerous-route denominator do not depend on the configuration
    assert ev.n_dangerous_ai_routes.nunique() == 1
    assert ev.n_noncritical_ai_correct.nunique() == 1


@NEEDS_OUTPUTS
def test_dangerous_misroutes_are_scored_from_ground_truth_only_here(decisions):
    fw = decisions[decisions.configuration == "decision_firewall"]
    # the scoring columns exist only in the evaluation output ...
    assert {"true_dept", "critical_case", "ai_dangerous_misroute"} <= set(fw.columns)
    # ... and the runtime module never mentions ground truth anywhere in its source
    src = inspect.getsource(decision_firewall)
    body = src.replace('"true_dept" in firewall_input', "").replace("(true_dept)", "").replace("(`true_dept`)", "")
    assert "true_dept" not in body


@NEEDS_OUTPUTS
def test_ai_only_allows_dangerous_misroutes_and_firewall_intercepts_them(decisions):
    ev = aggregate(decisions).set_index("configuration")
    assert ev.loc["ai_only", "dangerous_misroutes_allowed"] == ev.loc["ai_only", "n_dangerous_ai_routes"] > 0
    assert ev.loc["decision_firewall", "dangerous_misroutes_allowed"] == 0
    assert ev.loc["decision_firewall", "critical_emergency_response"] == ev.loc["decision_firewall", "n_critical_cases"]
    # and it still keeps most correct low-risk routes automatic
    assert ev.loc["decision_firewall", "safe_automation_count"] > 0


@NEEDS_OUTPUTS
def test_unnecessary_escalation_excludes_true_critical_cases(decisions):
    fw = decisions[decisions.configuration == "decision_firewall"]
    assert not fw[fw.critical_case].unnecessary_escalation.any()
    assert not fw[~fw.ai_correct].unnecessary_escalation.any()
    assert fw[fw.unnecessary_escalation].escalated.all()


@NEEDS_OUTPUTS
def test_escalate_everything_has_poor_workload_metrics(decisions):
    ev = aggregate(decisions).set_index("configuration")
    ref = ev.loc["escalate_everything"]
    assert ref.human_review_rate == 1.0
    assert ref.safe_automation_rate == 0.0
    assert ref.unnecessary_escalation_rate == 1.0
    fw = ev.loc["decision_firewall"]
    assert fw.human_review_rate < ref.human_review_rate
    assert fw.safe_automation_rate > ref.safe_automation_rate
    assert fw.unnecessary_escalation_rate < ref.unnecessary_escalation_rate


@NEEDS_OUTPUTS
def test_results_are_deterministic(world, decisions):
    cfg, complaints, graph, ranking, scenarios = world
    again = evaluate_cases(complaints, scenarios, graph, ranking, cfg)
    pd.testing.assert_frame_equal(decisions, again)


@NEEDS_OUTPUTS
def test_asset_impact_only_for_mapped_scenarios(decisions):
    fw = decisions[decisions.configuration == "decision_firewall"]
    assert fw[fw.mapped_scenario_id == ""].simulated_exposure.isna().all()
    assert (fw[fw.mapped_scenario_id == ""].asset_id.eq("") | fw[fw.mapped_scenario_id == ""].complaint_id.isin(fw[fw.mapped_scenario_id != ""].complaint_id)).all()


@NEEDS_OUTPUTS
def test_canonical_trace_is_red_and_complete(world):
    cfg, complaints, graph, ranking, scenarios = world
    trace = build_decision_trace(cfg["firewall"]["canonical_scenario_id"], complaints, scenarios, graph, ranking, cfg)
    d = trace["decision"]
    assert d["risk_level"] == "red" and d["dispatch_immediate"] and d["human_review_required"]
    assert "DIRECT_HAZARD" in d["reason_codes"]
    assert trace["classifier"]["input_complete"] is False
    assert trace["asset_context"]["context_available"] is True
    assert trace["asset_context"]["criticality_tier"] in ("high", "very_high")
    assert trace["acknowledgement"]["unacknowledged_past_target"]["acknowledgement_state"] == "reescalated"
    assert trace["physical_outcome"]["ai_only"]["initiating_failure"] is True
    assert trace["physical_outcome"]["decision_firewall"]["initiating_failure"] is False
    assert trace["physical_outcome"]["ai_only"]["cascade"]["people_affected"] > 0


def test_scenarios_reject_conflicting_asset_mappings(tmp_path, monkeypatch):
    import evaluate_firewall as ef

    bad = tmp_path / "scenarios.csv"
    bad.write_text(
        "scenario_id,complaint_id,language,condition,asset_id,asset_mapping_method,structured_hazard,structured_immediate_danger,scenario_failure_window_hours,provenance,notes\n"
        "S1,c01,native,clean,sub_001,scenario_selected,,false,336,synthetic_scenario,x\n"
        "S2,c01,en,clean,sub_002,scenario_selected,,false,336,synthetic_scenario,y\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ef, "DATA_DIR", tmp_path)
    with pytest.raises(ValueError):
        ef.load_scenarios()


def test_missing_ranking_gives_actionable_error(tmp_path, monkeypatch):
    import evaluate_firewall as ef

    monkeypatch.setattr(ef, "OUTPUTS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="d1_cascade.py"):
        ef.load_full_ranking()
    (tmp_path / "d1_criticality.csv").write_text("node_id,name,people_affected\nsub_001,x,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="legacy"):
        ef.load_full_ranking()
