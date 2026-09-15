"""Comparative safety evaluation: AI only vs. the existing guard vs. the Decision Firewall.

This is the ONLY module allowed to read ground truth (`true_dept`). It scores the runtime
decisions after the fact; the Firewall itself (decision_firewall.py) never sees it.

Evaluation matrix: the existing 20 synthetic complaints x 2 languages x 3 classifier
conditions = 120 cases. Asset context is attached only to complaints that have an explicit
mapping in data/scenarios.csv; nothing is silently attached to the most critical asset.
The Firewall is evaluated on free text only (no structured intake answers) so the result
reflects the independent original-text scan; the structured path is demonstrated in the app.

Configurations:
  ai_only                              classifier route accepted automatically
  existing_guard                       d2_language.route_with_guard() (same degraded input)
  decision_firewall                    full policy, reliability state from the controlled canary
  decision_firewall_reliability_normal same policy with safe mode switched off (attribution)
  escalate_everything                  reference: every complaint to human review

Outputs:
  outputs/firewall_decisions.csv   one auditable row per case x configuration
  outputs/firewall_evaluation.csv  counts, denominators and rates per configuration
  outputs/firewall_comparison.png  compact benefit/cost chart
  outputs/decision_trace.json      the canonical demo scenario, end to end
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cascade import cascade, summarize_final  # noqa: E402
from d2_language import CONDITIONS, LANGUAGES, canary_report, route_with_guard  # noqa: E402
from decision_firewall import (  # noqa: E402
    advance_acknowledgement,
    build_asset_context,
    reliability_state_from_canary,
    run_firewall,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs"
DATA_DIR = REPO_ROOT / "data"

CONFIGURATIONS = [
    "ai_only",
    "existing_guard",
    "decision_firewall",
    "decision_firewall_reliability_normal",
    "escalate_everything",
]
PRIMARY_CONFIGURATIONS = ["ai_only", "existing_guard", "decision_firewall"]
LABELS = {
    "ai_only": "AI only",
    "existing_guard": "Existing guard",
    "decision_firewall": "Decision Firewall",
    "decision_firewall_reliability_normal": "Firewall, safe mode off",
    "escalate_everything": "Escalate everything (reference)",
}


# --------------------------------------------------------------------------- loading


def load_config() -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_graph() -> nx.DiGraph:
    path = DATA_DIR / "processed" / "graph.gpickle"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run `python src/build_graph.py` first.")
    with open(path, "rb") as f:
        return pickle.load(f)


def load_full_ranking() -> pd.DataFrame:
    """The FULL criticality ranking written by d1_cascade.py (every substation, with rank)."""
    path = OUTPUTS_DIR / "d1_criticality.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run `python src/d1_cascade.py` first.")
    df = pd.read_csv(path)
    if "rank" not in df.columns or "criticality_percentile" not in df.columns:
        raise ValueError(f"{path} is a legacy top-N slice without rank/percentile — rerun `python src/d1_cascade.py`.")
    return df


def load_complaints() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "complaints.csv")


def load_scenarios(complaints: pd.DataFrame | None = None, graph: nx.DiGraph | None = None) -> pd.DataFrame:
    """data/scenarios.csv with validation: one asset per complaint, assets exist, ids resolve."""
    path = DATA_DIR / "scenarios.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — the canonical scenario mapping is required.")
    df = pd.read_csv(path, dtype={"structured_hazard": "string"})
    df["structured_hazard"] = df["structured_hazard"].fillna("")
    df["structured_immediate_danger"] = df["structured_immediate_danger"].astype(str).str.lower().isin(["true", "1", "yes"])
    multi = df.groupby("complaint_id")["asset_id"].nunique()
    if (multi > 1).any():
        raise ValueError(f"scenarios.csv maps a complaint to more than one asset: {multi[multi > 1].index.tolist()}")
    if complaints is not None:
        unknown = set(df.complaint_id) - set(complaints.id)
        if unknown:
            raise ValueError(f"scenarios.csv references unknown complaint ids: {sorted(unknown)}")
    if graph is not None:
        missing = [a for a in df.asset_id.dropna().unique() if a not in graph]
        if missing:
            raise ValueError(f"scenarios.csv references assets that are not in the graph: {missing}")
    return df


# --------------------------------------------------------------------------- per-case evaluation


def _critical_departments(cfg: dict[str, Any]) -> set[str]:
    thr = cfg["firewall"]["critical_sla_threshold_hours"]
    return {d for d, h in cfg["d2"]["sla_hours"].items() if d != "verification" and h <= thr}


def evaluate_cases(
    complaints: pd.DataFrame,
    scenarios: pd.DataFrame,
    graph: nx.DiGraph,
    ranking: pd.DataFrame,
    cfg: dict[str, Any],
    configurations: list[str] | None = None,
) -> pd.DataFrame:
    """One row per (case, configuration). Ground truth is used here — and only here — to score."""
    configurations = configurations or CONFIGURATIONS
    fw = cfg["firewall"]
    critical_depts = _critical_departments(cfg)
    thr = fw["critical_sla_threshold_hours"]
    canary = canary_report(complaints, cfg["d2"])
    asset_by_complaint = {r.complaint_id: r for r in scenarios.itertuples()}
    contexts = {a: build_asset_context(graph, a, ranking, cfg, "scenario_selected") for a in scenarios.asset_id.dropna().unique()}
    scenario_by_case = {(r.complaint_id, r.language, r.condition): r for r in scenarios.itertuples()}

    rows: list[dict[str, Any]] = []
    for _, c in complaints.iterrows():
        true_dept = c["true_dept"]
        critical = true_dept in critical_depts
        mapping = asset_by_complaint.get(c["id"])
        ctx = contexts[mapping.asset_id] if mapping is not None else None
        window = float(mapping.scenario_failure_window_hours) if mapping is not None and not pd.isna(mapping.scenario_failure_window_hours) else None
        for lang, col in LANGUAGES.items():
            text = c[col]
            for cond in CONDITIONS:
                rel = reliability_state_from_canary(canary, lang, cond, cfg)
                base_trace = run_firewall(c["id"], text, lang, cond, cfg, asset_context=ctx, reliability_state=rel,
                                          scenario_failure_window_hours=window)
                clf = base_trace["classifier"]
                pred = clf["predicted_dept"]
                ai_correct = pred == true_dept
                ai_route = base_trace["ai_only"]["department"]
                ai_dangerous = critical and ai_route not in critical_depts
                scen = scenario_by_case.get((c["id"], lang, cond))
                exposure = ctx["simulated_people_exposed"] if ctx else None

                for config in configurations:
                    out = _apply_configuration(config, base_trace, text, cond, lang, ctx, cfg, true_dept)
                    human_review = out["human_review"]
                    emergency = out["emergency_dispatch"]
                    automatic = out["action"] == "automatic_route"
                    response = out["response_hours"]
                    final_dept = out["final_department"]
                    allowed = critical and automatic and (final_dept not in critical_depts) and (response is None or response > thr)
                    escalated = human_review or emergency
                    rows.append({
                        "configuration": config,
                        "case_id": f"{c['id']}_{lang}_{cond}",
                        "complaint_id": c["id"],
                        "language": lang,
                        "condition": cond,
                        "true_dept": true_dept,                      # ground truth: evaluation only
                        "critical_case": critical,
                        "predicted_dept": pred or "",
                        "prediction_margin": clf["margin"],
                        "classifier_input_complete": clf["input_complete"],
                        "ai_only_route": ai_route,
                        "ai_correct": ai_correct,
                        "ai_dangerous_misroute": ai_dangerous,
                        "asset_id": ctx["asset_id"] if ctx else "",
                        "criticality_tier": ctx["criticality_tier"] if ctx else "unknown",
                        "reliability_state": out["reliability_state"],
                        "risk_level": out["risk_level"],
                        "action": out["action"],
                        "final_department": final_dept,
                        "human_review": human_review,
                        "emergency_dispatch": emergency,
                        "response_hours": response,
                        "reason_codes": "|".join(out["reason_codes"]),
                        "dangerous_misroute_allowed": allowed,
                        "dangerous_misroute_intercepted": ai_dangerous and not allowed,
                        "critical_emergency_response": critical and response is not None and response <= thr,
                        "escalated": escalated,
                        "unnecessary_escalation": (not critical) and ai_correct and escalated,
                        "noncritical_misroute_caught": (not critical) and (not ai_correct) and escalated,
                        # automatic AND at normal priority: an urgency-floored automatic route is not "safe automation"
                        "safe_automation": (not critical) and ai_correct and automatic and not escalated,
                        "mapped_scenario_id": scen.scenario_id if scen is not None else "",
                        "failure_window_hours": window if scen is not None else None,
                        "incident_prevented": (scen is not None and critical and response is not None and window is not None and response < window),
                        "simulated_exposure": exposure if scen is not None and critical else None,
                    })
    return pd.DataFrame(rows)


def _apply_configuration(config: str, trace: dict[str, Any], text: str, condition: str, language: str,
                         ctx: dict[str, Any] | None, cfg: dict[str, Any], true_dept: str) -> dict[str, Any]:
    """Map one configuration to (risk_level, action, final dept, review, dispatch, response hours).

    Response hours (ASSUMED model): automatic route -> that department's SLA (right or wrong);
    human verification -> review target + the true department's SLA (assumes the verifier
    corrects the route); emergency dispatch -> the emergency response time.
    """
    sla = cfg["d2"]["sla_hours"]
    fw = cfg["firewall"]
    emergency_hours = float(fw.get("emergency_response_hours", sla["electrical_emergency"]))

    if config == "ai_only":
        dept = trace["ai_only"]["department"]
        return {"risk_level": "n/a", "action": "automatic_route", "final_department": dept, "human_review": False,
                "emergency_dispatch": False, "response_hours": float(sla[dept]), "reason_codes": [], "reliability_state": "n/a"}

    if config == "existing_guard":
        g = route_with_guard(text, condition, cfg["d2"])
        queue = g["guarded"]["queue"]
        floor = "urgency_floor" in g["flags"]
        if queue == "verification":
            response = float(sla["verification"]) + float(sla[true_dept])
            if floor:
                response = min(response, float(g["guarded"]["sla_hours"]))
            return {"risk_level": "verification", "action": "human_verification", "final_department": "verification",
                    "human_review": True, "emergency_dispatch": floor, "response_hours": response,
                    "reason_codes": g["flags"], "reliability_state": "n/a"}
        return {"risk_level": "urgency_floor" if floor else "n/a", "action": "automatic_route", "final_department": queue,
                "human_review": False, "emergency_dispatch": floor, "response_hours": float(g["guarded"]["sla_hours"]),
                "reason_codes": g["flags"], "reliability_state": "n/a"}

    if config == "escalate_everything":
        return {"risk_level": "yellow", "action": "human_verification", "final_department": "verification", "human_review": True,
                "emergency_dispatch": False, "response_hours": float(fw["action_policy"]["yellow_review_target_hours"]) + float(sla[true_dept]),
                "reason_codes": ["ESCALATE_ALL"], "reliability_state": "n/a"}

    if config == "decision_firewall_reliability_normal":
        trace = run_firewall(trace["complaint_id"], text, language, condition, cfg, asset_context=ctx, reliability_state="normal",
                             scenario_failure_window_hours=trace["firewall_input"]["scenario_failure_window_hours"])
    elif config != "decision_firewall":
        raise ValueError(f"unknown configuration {config!r}")

    d = trace["decision"]
    level = d["risk_level"]
    if level == "red":
        response = emergency_hours
    elif level == "yellow":
        response = float(fw["action_policy"]["yellow_review_target_hours"]) + float(sla[true_dept])
    else:
        response = float(sla[d["final_department"]])
    return {"risk_level": level, "action": d["action"], "final_department": d["final_department"],
            "human_review": d["human_review_required"], "emergency_dispatch": d["dispatch_immediate"],
            "response_hours": response, "reason_codes": d["reason_codes"],
            "reliability_state": trace["firewall_input"]["reliability_state"]}


# --------------------------------------------------------------------------- aggregation


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def aggregate(decisions: pd.DataFrame) -> pd.DataFrame:
    """Counts, denominators and rates per configuration. Every rate carries its denominator."""
    rows = []
    for config, df in decisions.groupby("configuration", sort=False):
        n = len(df)
        crit = df[df.critical_case]
        dangerous = df[df.ai_dangerous_misroute]
        noncrit_ok = df[(~df.critical_case) & df.ai_correct]
        noncrit_bad = df[(~df.critical_case) & (~df.ai_correct)]
        mapped = df[(df.mapped_scenario_id != "") & df.critical_case]
        baseline = decisions[(decisions.configuration == "ai_only") & (decisions.mapped_scenario_id != "") & decisions.critical_case]
        base_incurred = baseline[~baseline.incident_prevented]["simulated_exposure"].fillna(0).sum()
        incurred = mapped[~mapped.incident_prevented]["simulated_exposure"].fillna(0).sum()
        rows.append({
            "configuration": config,
            "label": LABELS.get(config, config),
            "n_cases": n,
            "n_critical_cases": len(crit),
            "n_dangerous_ai_routes": len(dangerous),
            "dangerous_misroutes_allowed": int(dangerous.dangerous_misroute_allowed.sum()),
            "dangerous_misroutes_intercepted": int(dangerous.dangerous_misroute_intercepted.sum()),
            "critical_incident_catch_rate": _rate(int(dangerous.dangerous_misroute_intercepted.sum()), len(dangerous)),
            "critical_emergency_response": int(crit.critical_emergency_response.sum()),
            "critical_emergency_response_rate": _rate(int(crit.critical_emergency_response.sum()), len(crit)),
            "human_review_count": int(df.human_review.sum()),
            "human_review_rate": _rate(int(df.human_review.sum()), n),
            "emergency_dispatch_count": int(df.emergency_dispatch.sum()),
            "emergency_dispatch_rate": _rate(int(df.emergency_dispatch.sum()), n),
            "n_noncritical_ai_correct": len(noncrit_ok),
            "unnecessary_escalations": int(noncrit_ok.unnecessary_escalation.sum()),
            "unnecessary_escalation_rate": _rate(int(noncrit_ok.unnecessary_escalation.sum()), len(noncrit_ok)),
            "safe_automation_count": int(noncrit_ok.safe_automation.sum()),
            "safe_automation_rate": _rate(int(noncrit_ok.safe_automation.sum()), len(noncrit_ok)),
            "n_noncritical_ai_wrong": len(noncrit_bad),
            "noncritical_misroutes_caught": int(noncrit_bad.noncritical_misroute_caught.sum()),
            "noncritical_misroutes_caught_rate": _rate(int(noncrit_bad.noncritical_misroute_caught.sum()), len(noncrit_bad)),
            "n_mapped_critical_scenarios": len(mapped),
            "simulated_incidents_prevented": int(mapped.incident_prevented.sum()),
            "simulated_incidents_prevented_rate": _rate(int(mapped.incident_prevented.sum()), len(mapped)),
            "simulated_exposure_incurred": int(incurred),
            "simulated_exposure_avoided_vs_ai_only": int(base_incurred - incurred),
        })
    return pd.DataFrame(rows)


def aggregate_by(decisions: pd.DataFrame, by: str) -> pd.DataFrame:
    """The same counts split by `by` (e.g. condition or language) so the workload cost of safe
    mode / truncation shows where it comes from instead of being averaged away."""
    frames = []
    for value, part in decisions.groupby(by, sort=False):
        agg = aggregate(part)
        agg.insert(1, by, value)
        frames.append(agg)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- chart


def plot_comparison(evaluation: pd.DataFrame, out_path: Path | None, configurations: list[str] | None = None) -> plt.Figure:
    """Benefit and cost side by side: dangerous routes intercepted, safe automation kept,
    human-review load, unnecessary escalations — all as count / denominator."""
    configurations = configurations or PRIMARY_CONFIGURATIONS
    ev = evaluation.set_index("configuration").loc[configurations]
    metrics = [
        ("Dangerous AI routes\nintercepted", "dangerous_misroutes_intercepted", "n_dangerous_ai_routes", "#34a853"),
        ("Critical cases with\nemergency-speed response", "critical_emergency_response", "n_critical_cases", "#34a853"),
        ("Correct low-risk routes\nkept automatic", "safe_automation_count", "n_noncritical_ai_correct", "#4285f4"),
        ("Decisions needing\nhuman review (cost)", "human_review_count", "n_cases", "#f5a623"),
        ("Unnecessary\nescalations (cost)", "unnecessary_escalations", "n_noncritical_ai_correct", "#d93025"),
    ]
    fig, axes = plt.subplots(1, len(metrics), figsize=(15, 4.6), dpi=150)
    colors = {"ai_only": "#9aa0a6", "existing_guard": "#4285f4", "decision_firewall": "#d93025",
              "decision_firewall_reliability_normal": "#f5a623", "escalate_everything": "#6b7280"}
    for ax, (title, num_col, den_col, _) in zip(axes, metrics):
        vals = [ev.loc[c, num_col] for c in configurations]
        dens = [ev.loc[c, den_col] for c in configurations]
        bars = ax.bar(range(len(configurations)), vals, color=[colors[c] for c in configurations])
        ax.set_xticks(range(len(configurations)))
        ax.set_xticklabels([LABELS[c].replace(" ", "\n", 1) for c in configurations], fontsize=8.5)
        ax.set_title(title, fontsize=10.5)
        top = max(dens) if max(dens) else 1
        ax.set_ylim(0, top * 1.22)
        for b, v, d in zip(bars, vals, dens):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + top * 0.02, f"{int(v)}/{int(d)}", ha="center", fontsize=9.5, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Decision Firewall vs. AI-only routing — controlled set: 20 complaints x 2 languages x 3 conditions (measured)",
                 fontsize=11.5)
    fig.tight_layout()
    if out_path is not None:
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"[evaluate_firewall] wrote {out_path}")
    return fig


# --------------------------------------------------------------------------- canonical trace


def build_decision_trace(
    scenario_id: str,
    complaints: pd.DataFrame,
    scenarios: pd.DataFrame,
    graph: nx.DiGraph,
    ranking: pd.DataFrame,
    cfg: dict[str, Any],
    reliability_override: str | None = None,
) -> dict[str, Any]:
    """The complete auditable trace for one scenario: complaint -> classifier -> independent
    scan -> asset context -> reliability -> decision -> action plan -> acknowledgement ->
    AI-only vs Firewall physical outcome (simulated)."""
    rows = scenarios[scenarios.scenario_id == scenario_id]
    if rows.empty:
        raise ValueError(f"scenario {scenario_id!r} not in data/scenarios.csv")
    s = rows.iloc[0]
    c = complaints[complaints.id == s.complaint_id].iloc[0]
    text = c["text_native"] if s.language == "native" else c["text_en"]
    canary = canary_report(complaints, cfg["d2"])
    rel = reliability_override or reliability_state_from_canary(canary, s.language, s.condition, cfg)
    ctx = build_asset_context(graph, s.asset_id, ranking, cfg, s.asset_mapping_method)
    window = float(s.scenario_failure_window_hours) if not pd.isna(s.scenario_failure_window_hours) else None
    structured = [h for h in str(s.structured_hazard).split(";") if h]
    trace = run_firewall(s.complaint_id, text, s.language, s.condition, cfg, structured_hazards=structured,
                         immediate_danger=bool(s.structured_immediate_danger), asset_context=ctx, reliability_state=rel,
                         scenario_failure_window_hours=window)
    fw = cfg["firewall"]
    plan = trace["action_plan"]
    ack_target = fw["action_policy"]["red_reescalation_target_minutes"]
    acknowledgement = {
        "awaiting": advance_acknowledgement(plan, False, 0, fw),
        "acknowledged": advance_acknowledgement(plan, True, 5, fw),
        "unacknowledged_past_target": advance_acknowledgement(plan, False, ack_target, fw),
    }
    outcome = physical_outcome(trace, ctx, graph, cfg)
    return {
        "scenario": {k: (None if (isinstance(v, float) and pd.isna(v)) else (v.item() if hasattr(v, "item") else v)) for k, v in s.to_dict().items()},
        "complaint": {"id": c["id"], "text_en": c["text_en"], "text_native": c["text_native"], "provenance": "synthetic"},
        "language": s.language,
        "condition": s.condition,
        "reliability_state": rel,
        "classifier": trace["classifier"],
        "safety_scan": trace["safety_scan"],
        "asset_context": ctx,
        "firewall_input": trace["firewall_input"],
        "decision": trace["decision"],
        "action_plan": plan,
        "acknowledgement": acknowledgement,
        "physical_outcome": outcome,
        "labels": {
            "complaint": "synthetic", "asset_mapping": "synthetic (scenario-selected)", "classifier_result": "measured (prototype classifier)",
            "safety_scan": "measured (rule-based)", "policy_thresholds": "assumed prototype policy", "failure_window": "assumed",
            "cascade": "simulated", "exposure": "simulated service population, not unique people",
        },
    }


def physical_outcome(trace: dict[str, Any], ctx: dict[str, Any], graph: nx.DiGraph, cfg: dict[str, Any]) -> dict[str, Any]:
    """AI-only vs Firewall under the declared scenario assumption: if the response arrives at or
    after the assumed failure window, the initiating failure occurs and the corrected cascade
    runs; otherwise it is prevented. Simulated, not predicted."""
    window = trace["firewall_input"]["scenario_failure_window_hours"]
    ai_hours = trace["ai_only"]["response_hours"]
    fw_hours = trace["response_hours"]

    def branch(hours: float | None, label: str) -> dict[str, Any]:
        if window is None or hours is None or not ctx.get("context_available"):
            return {"label": label, "response_hours": hours, "failure_window_hours": window, "initiating_failure": None,
                    "note": "no failure window or asset context: physical outcome not evaluated"}
        fails = hours >= window
        out = {"label": label, "response_hours": hours, "failure_window_hours": window, "initiating_failure": fails}
        if fails:
            tl = cascade(graph, [ctx["asset_id"]], max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"])
            out["cascade"] = summarize_final(tl)
        else:
            out["cascade"] = {k: 0 for k in ("people_affected", "substations_failed", "cascade_size", "hospitals_on_backup", "hospitals_without_power", "pumps_without_water")}
        return out

    return {
        "assumption": "the initiating failure occurs only if the response arrives at or after the assumed failure window",
        "ai_only": branch(ai_hours, "AI only"),
        "decision_firewall": branch(fw_hours, "Decision Firewall"),
    }


def _json_default(o: Any) -> Any:
    if isinstance(o, set):
        return sorted(o)
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, float) and pd.isna(o):
        return None
    return str(o)


# --------------------------------------------------------------------------- main


def main() -> None:
    cfg = load_config()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    complaints = load_complaints()
    graph = load_graph()
    ranking = load_full_ranking()
    scenarios = load_scenarios(complaints, graph)
    print(f"[evaluate_firewall] {len(complaints)} complaints, {len(scenarios)} scenario mappings, {len(ranking)} ranked assets")

    decisions = evaluate_cases(complaints, scenarios, graph, ranking, cfg)
    decisions.to_csv(OUTPUTS_DIR / "firewall_decisions.csv", index=False)
    print(f"[evaluate_firewall] wrote {OUTPUTS_DIR / 'firewall_decisions.csv'} ({len(decisions)} rows)")

    evaluation = aggregate(decisions)
    evaluation.to_csv(OUTPUTS_DIR / "firewall_evaluation.csv", index=False)
    print(f"[evaluate_firewall] wrote {OUTPUTS_DIR / 'firewall_evaluation.csv'}")
    show = ["label", "dangerous_misroutes_intercepted", "n_dangerous_ai_routes", "critical_emergency_response", "n_critical_cases",
            "human_review_count", "emergency_dispatch_count", "n_cases", "unnecessary_escalations", "safe_automation_count",
            "n_noncritical_ai_correct", "simulated_incidents_prevented", "n_mapped_critical_scenarios", "simulated_exposure_avoided_vs_ai_only"]
    print(evaluation[show].to_string(index=False))

    by_condition = aggregate_by(decisions, "condition")
    by_condition.to_csv(OUTPUTS_DIR / "firewall_evaluation_by_condition.csv", index=False)
    print(f"[evaluate_firewall] wrote {OUTPUTS_DIR / 'firewall_evaluation_by_condition.csv'}")
    print(by_condition[by_condition.configuration.isin(PRIMARY_CONFIGURATIONS)][
        ["label", "condition", "dangerous_misroutes_intercepted", "n_dangerous_ai_routes", "human_review_count", "n_cases",
         "unnecessary_escalations", "safe_automation_count", "n_noncritical_ai_correct"]].to_string(index=False))

    plot_comparison(evaluation, OUTPUTS_DIR / "firewall_comparison.png")

    trace = build_decision_trace(cfg["firewall"]["canonical_scenario_id"], complaints, scenarios, graph, ranking, cfg)
    with open(OUTPUTS_DIR / "decision_trace.json", "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2, default=_json_default)
    print(f"[evaluate_firewall] wrote {OUTPUTS_DIR / 'decision_trace.json'}: "
          f"{trace['decision']['risk_level'].upper()} {trace['decision']['action']} -> {trace['decision']['reason_codes']}")


if __name__ == "__main__":
    main()
