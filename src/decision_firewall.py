"""Silent Cascade Decision Firewall — pure, deterministic policy functions.

A consequence-aware safety and dispatch layer placed between an AI complaint classifier and
municipal operations. The AI proposes a route; the Firewall decides how much authority the AI
is allowed to exercise:

    GREEN  -> automatic routing (AI autonomy allowed)
    YELLOW -> AI route is a recommendation only; rapid human verification before final routing
    RED    -> immediate simulated emergency work order; human review in parallel; AI overridden

Design rules (CLAUDE.md sections 4, 8-12):
* the safety scan reads the COMPLETE ORIGINAL complaint plus structured intake answers — never
  the truncated/degraded text the classifier saw, and never the classifier's prediction;
* unknown risk is not low risk: missing classifier output, missing asset context or an
  unavailable reliability state can never silently become Green;
* mandatory Red overrides take priority over every other signal;
* nothing here reads ground truth (`true_dept`). Ground truth is used only in
  evaluate_firewall.py to score the decisions afterwards.

Every function takes and returns plain dictionaries so the app, the evaluation script and the
tests all exercise exactly the same code. No file I/O, no network, no model calls.
"""

from __future__ import annotations

import math
from typing import Any

import networkx as nx
import pandas as pd

from d2_language import (
    DEPARTMENTS,
    SAFETY_KEYWORDS_EN,
    SAFETY_KEYWORDS_KN,
    _looks_english,
    classify_scores,
    condition_input,
)

# --------------------------------------------------------------------------- vocabulary

HAZARDS = [
    "electrical_sparking",
    "live_wire",
    "electric_shock",
    "fire_or_burning",
    "burst_pipe",
    "active_flooding",
    "unknown_immediate_danger",
]

# Text vocabulary for the independent safety scan. Every term below is either already in
# d2_language.SAFETY_KEYWORDS_* or appears verbatim in data/complaints.csv; nothing was added
# after seeing evaluation results. Known collision, kept deliberately rather than hidden:
# Kannada "ಒಡೆದ" (broken/burst) also matches c17's broken footpath tiles ("ಒಡೆದು"), so that
# roads complaint carries a burst_pipe signal in Kannada. burst_pipe is a *service* hazard,
# not a mandatory-Red hazard, so the effect is at most a Yellow conflict flag.
HAZARD_TERMS_EN: dict[str, list[str]] = {
    "electrical_sparking": ["spark", "sparks", "sparking"],
    "live_wire": ["live wire", "exposed wire", "exposed electric wire"],
    "electric_shock": ["shock"],
    "fire_or_burning": ["fire", "burning"],
    "burst_pipe": ["burst"],
    "active_flooding": ["flooding"],
}
HAZARD_TERMS_KN: dict[str, list[str]] = {
    "electrical_sparking": ["ಕಿಡಿ"],
    "live_wire": ["ವಿದ್ಯುತ್ ತಂತಿ"],
    "electric_shock": ["ಶಾಕ್"],
    "fire_or_burning": ["ಬೆಂಕಿ", "ಸುಟ್ಟ ವಾಸನೆ"],
    "burst_pipe": ["ಒಡೆದ"],
    # no Kannada free-text term for active flooding in the controlled set: in Kannada this
    # hazard is reachable through the structured intake path only (documented limitation)
    "active_flooding": [],
}

# Structured intake labels a citizen / call-centre operator can tick, mapped to hazards.
STRUCTURED_HAZARD_ALIASES: dict[str, str] = {
    "sparks": "electrical_sparking", "sparking": "electrical_sparking", "electrical_sparking": "electrical_sparking",
    "fire": "fire_or_burning", "burning": "fire_or_burning", "smoke": "fire_or_burning", "fire_or_burning": "fire_or_burning",
    "live_wire": "live_wire", "exposed_wire": "live_wire", "exposed wire": "live_wire", "live wire": "live_wire",
    "shock": "electric_shock", "electric_shock": "electric_shock",
    "burst_pipe": "burst_pipe", "burst pipe": "burst_pipe",
    "flooding": "active_flooding", "active_flooding": "active_flooding",
    "immediate_danger": "unknown_immediate_danger", "unknown_immediate_danger": "unknown_immediate_danger",
}

REASON_TEXT: dict[str, str] = {
    "DIRECT_HAZARD": "The original complaint or intake form reports an immediate physical hazard ({detail}).",
    "STRUCTURED_IMMEDIATE_DANGER": "The intake form explicitly marks this complaint as immediate danger.",
    "DANGEROUS_DOWNGRADE": "A time-critical hazard was routed to a slower, non-critical route ({detail}).",
    "LOW_MARGIN": "The classifier's score margin ({detail}) is below the configured threshold — an uncertainty signal, not a probability.",
    "UNPARSEABLE_CLASSIFICATION": "The classifier returned no department at all.",
    "TRUNCATED_CLASSIFIER_INPUT": "The classifier saw a truncated or incomplete version of the complaint.",
    "VERY_HIGH_ASSET_CRITICALITY": "The affected asset is in the top simulated-consequence tier ({detail}).",
    "HIGH_ASSET_CRITICALITY": "The affected asset is in the high simulated-consequence tier ({detail}).",
    "REPAIR_WINDOW_AT_RISK": "The proposed route's repair time ({detail}) reaches the assumed failure window.",
    "RELIABILITY_DEGRADED": "The routing quality check for this language/condition is degraded — safe mode restricts automatic routing.",
    "RELIABILITY_UNAVAILABLE": "No routing quality signal is available — unknown reliability is not treated as reliable.",
    "ASSET_CONTEXT_MISSING": "No infrastructure asset context is available for an infrastructure complaint ({detail}).",
    "CONFLICTING_SIGNALS": "The independent hazard scan and the AI department disagree ({detail}).",
    "MISSING_REQUIRED_FIELD": "A required input is missing ({detail}).",
    "SAFE_AUTOMATION_ALLOWED": "All required context is present, no hazard or uncertainty signal fired, reliability is normal.",
}

TIER_ORDER = {"unknown": -1, "normal": 0, "high": 1, "very_high": 2}


# --------------------------------------------------------------------------- 1. safety scan


def detect_safety_hazards(
    original_text: str,
    language: str,
    structured_hazards: list[str] | None = None,
    immediate_danger: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect explicit hazards independently of the AI classification path.

    Scans the COMPLETE original text (never condition_input()'s truncated text) in the
    detected/selected language, then merges structured intake answers. Returns matched terms
    with their source and language, normalized hazard categories, and the immediate-danger
    state. Does not look at any department prediction.
    """
    text = original_text or ""
    if language not in ("en", "native"):
        language = "en" if _looks_english(text) else "native"
    vocab = HAZARD_TERMS_EN if language == "en" else HAZARD_TERMS_KN
    legacy_terms = set(SAFETY_KEYWORDS_EN if language == "en" else SAFETY_KEYWORDS_KN)
    low = text.lower()

    matches: list[dict[str, Any]] = []
    hazards: list[str] = []
    for hazard, terms in vocab.items():
        for term in terms:
            if term.lower() in low:
                matches.append({"term": term, "language": language, "hazard": hazard, "source": "original_text",
                                "in_legacy_guard_vocabulary": term in legacy_terms})
                if hazard not in hazards:
                    hazards.append(hazard)

    for raw in structured_hazards or []:
        key = str(raw).strip().lower()
        if not key:
            continue
        hazard = STRUCTURED_HAZARD_ALIASES.get(key)
        if hazard is None:
            hazard = "unknown_immediate_danger"
        matches.append({"term": raw, "language": "structured", "hazard": hazard, "source": "structured_intake",
                        "in_legacy_guard_vocabulary": False})
        if hazard not in hazards:
            hazards.append(hazard)

    if immediate_danger:
        matches.append({"term": "immediate_danger=true", "language": "structured", "hazard": "unknown_immediate_danger",
                        "source": "structured_intake", "in_legacy_guard_vocabulary": False})
        if "unknown_immediate_danger" not in hazards:
            hazards.append("unknown_immediate_danger")

    mandatory = set((policy or {}).get("mandatory_red_hazards", ["electrical_sparking", "live_wire", "electric_shock", "fire_or_burning"]))
    hazard_depts = (policy or {}).get("hazard_departments", {})
    direct = [h for h in hazards if h in mandatory]
    service = [h for h in hazards if h not in mandatory and h != "unknown_immediate_danger"]
    required_depts = sorted({hazard_depts.get(h, "electrical_emergency") for h in direct})

    return {
        "language": language,
        "scanned_text_length": len(text),
        "matched_terms": matches,
        "hazards": hazards,
        "direct_hazards": direct,
        "service_hazards": service,
        "direct_hazard": bool(direct),
        "immediate_danger": bool(immediate_danger),
        "required_departments": required_depts,
        "provenance": {
            "text_scan": "measured_rule_based_scan_of_complete_original_text",
            "structured_intake": "synthetic_intake_answer" if (structured_hazards or immediate_danger) else "none_supplied",
            "vocabulary": "d2_language safety vocabulary + terms present in the controlled complaint set",
        },
    }


# --------------------------------------------------------------------------- 2. asset context


def criticality_tier(percentile: float | None, policy: dict[str, Any]) -> str:
    if percentile is None or (isinstance(percentile, float) and math.isnan(percentile)):
        return "unknown"
    cuts = policy["criticality_percentiles"]
    if percentile >= cuts["very_high"]:
        return "very_high"
    if percentile >= cuts["high"]:
        return "high"
    return "normal"


def build_asset_context(
    graph: nx.DiGraph | None,
    asset_id: str | None,
    criticality: pd.DataFrame | None,
    config: dict[str, Any],
    mapping_method: str = "scenario_selected",
) -> dict[str, Any]:
    """Return consequence context for the selected/reported asset.

    * validates that the asset exists in the graph and is a substation;
    * looks up rank/percentile in the FULL criticality ranking (not a top-10 slice);
    * returns ``context_available=False`` when anything is missing — it never falls back to
      the most critical substation, and it never treats proximity as feeder connectivity.
    """
    policy = config["firewall"]
    unavailable = {
        "context_available": False,
        "asset_id": asset_id,
        "asset_name": None,
        "mapping_method": mapping_method if asset_id else "none",
        "criticality_rank": None,
        "criticality_percentile": None,
        "criticality_tier": "unknown",
        "n_ranked_assets": int(len(criticality)) if criticality is not None else 0,
        "simulated_people_exposed": None,
        "simulated_substations_failed": None,
        "simulated_cascade_size": None,
        "dependent_hospitals": None,
        "dependent_water_assets": None,
        "hospitals_without_power": None,
        "wards_without_water": None,
        "reason": None,
        "provenance": _asset_provenance(mapping_method, available=False),
    }
    if not asset_id:
        return {**unavailable, "reason": "no asset supplied"}
    if graph is None or asset_id not in graph:
        return {**unavailable, "reason": f"asset {asset_id!r} is not in the graph"}
    if graph.nodes[asset_id].get("type") != "substation":
        return {**unavailable, "reason": f"asset {asset_id!r} is not a substation"}
    if criticality is None or criticality.empty or "node_id" not in criticality.columns:
        return {**unavailable, "reason": "criticality ranking unavailable"}
    rows = criticality[criticality["node_id"] == asset_id]
    if rows.empty:
        return {**unavailable, "reason": f"asset {asset_id!r} missing from the criticality ranking"}
    row = rows.iloc[0]
    n = int(len(criticality))
    rank = int(row["rank"]) if "rank" in criticality.columns else int(rows.index[0]) + 1
    pct = float(row["criticality_percentile"]) if "criticality_percentile" in criticality.columns else 100.0 * (1 - (rank - 1) / n)
    name = graph.nodes[asset_id].get("name") or ""

    def _int(col: str) -> int | None:
        return int(row[col]) if col in criticality.columns and not pd.isna(row[col]) else None

    hospitals = _int("hospitals_feeder_lost")
    pumps = _int("pumps_feeder_lost")
    return {
        "context_available": True,
        "asset_id": asset_id,
        "asset_name": name or asset_id,
        "mapping_method": mapping_method,
        "criticality_rank": rank,
        "criticality_percentile": round(pct, 2),
        "criticality_tier": criticality_tier(pct, policy),
        "n_ranked_assets": n,
        "simulated_people_exposed": _int("people_affected"),
        "simulated_substations_failed": _int("substations_failed"),
        "simulated_cascade_size": _int("cascade_size"),
        "dependent_hospitals": hospitals if hospitals is not None else _int("hospitals_hit"),
        "dependent_water_assets": pumps,
        "hospitals_without_power": _int("hospitals_without_power"),
        "wards_without_water": _int("pumps_without_water"),
        "reason": None,
        "provenance": _asset_provenance(mapping_method, available=True),
    }


def _asset_provenance(mapping_method: str, available: bool) -> dict[str, str]:
    mapping = {
        "scenario_selected": "synthetic: scenario-selected mapping, not evidence the complaint occurred here",
        "reported_asset": "synthetic: asset reported at intake in this scenario",
        "nearest_demo_only": "inferred (demo only): nearest substation by distance, NOT confirmed feeder connectivity",
        "none": "no mapping",
    }.get(mapping_method, mapping_method)
    return {
        "location": "observed (OpenStreetMap)" if available else "n/a",
        "topology": "inferred (3-nearest-neighbour grid edges, nearest-substation supply edges)",
        "capacities_loads": "assumed (config.yaml seeded draws)",
        "population": "assumed (config.yaml seeded draws; per-substation, not unique people)",
        "outcome": "simulated (corrected cascade engine, within the configured step horizon)",
        "asset_mapping": mapping,
    }


def nearest_substation_demo_only(graph: nx.DiGraph, lat: float, lon: float) -> dict[str, Any]:
    """Clearly-labelled DEMO fallback: nearest substation by great-circle distance. Geographic
    proximity is NOT confirmed electrical connectivity; the result carries that label."""
    best, best_km = None, math.inf
    for n, d in graph.nodes(data=True):
        if d.get("type") != "substation":
            continue
        km = _haversine_km(lat, lon, float(d["lat"]), float(d["lon"]))
        if km < best_km:
            best, best_km = n, km
    return {"asset_id": best, "distance_km": round(best_km, 3), "mapping_method": "nearest_demo_only",
            "label": "nearest asset by distance — demo approximation, not confirmed feeder connectivity"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------- 3. reliability state


def reliability_state_from_canary(
    report: pd.DataFrame | None,
    language: str,
    condition: str,
    config: dict[str, Any],
) -> str:
    """Return ``normal``, ``degraded`` or ``unavailable`` from the controlled canary report.

    * no report / missing cell -> ``unavailable`` (unknown reliability is not "normal");
    * native accuracy more than ``language_gap_degraded_pct`` below English under the same
      condition -> ``degraded`` for the native language;
    * accuracy more than ``drift_vs_clean_degraded_pct`` below the clean run for the same
      language -> ``degraded``;
    * otherwise ``normal``.
    This is a policy response to a SUPPLIED quality signal from a fixed golden set; it is not
    continuous production monitoring.
    """
    if report is None or report.empty:
        return "unavailable"
    rel = config["firewall"]["reliability"]
    try:
        cur = report[(report.condition == condition) & (report.language == language)].iloc[0]
        base = report[(report.condition == "clean") & (report.language == language)].iloc[0]
    except IndexError:
        return "unavailable"
    if language == "native":
        en_rows = report[(report.condition == condition) & (report.language == "en")]
        if en_rows.empty:
            return "unavailable"
        if float(en_rows.iloc[0]["accuracy_pct"]) - float(cur["accuracy_pct"]) > rel["language_gap_degraded_pct"]:
            return "degraded"
    if float(base["accuracy_pct"]) - float(cur["accuracy_pct"]) > rel["drift_vs_clean_degraded_pct"]:
        return "degraded"
    return "normal"


# --------------------------------------------------------------------------- 4. risk policy


def _sla(dept: str | None, config: dict[str, Any]) -> float | None:
    if not dept:
        return None
    return config["d2"]["sla_hours"].get(dept)


def assess_risk(
    firewall_input: dict[str, Any],
    safety_result: dict[str, Any],
    asset_context: dict[str, Any],
    policy: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assign Green, Yellow or Red and return explicit, stable reason codes.

    Mandatory Red overrides are evaluated first and take priority over everything else.
    Yellow rules run only if no Red rule fired. Green requires every Green condition.
    ``firewall_input`` must NOT contain ground truth; this function raises if it does.
    """
    if "true_dept" in firewall_input:
        raise ValueError("assess_risk() must never receive ground truth (true_dept)")
    cfg = config or {}
    sla_table = cfg.get("d2", {}).get("sla_hours", {})
    critical_threshold = policy.get("critical_sla_threshold_hours", 24)
    hazard_depts = policy.get("hazard_departments", {})

    pred = firewall_input.get("predicted_dept") or ""
    margin = firewall_input.get("prediction_margin")
    complete = bool(firewall_input.get("classifier_input_complete", False))
    reliability = firewall_input.get("reliability_state") or "unavailable"
    proposed_sla = firewall_input.get("proposed_sla_hours")
    window = firewall_input.get("scenario_failure_window_hours")
    tier = asset_context.get("criticality_tier", "unknown") if asset_context else "unknown"
    ctx_ok = bool(asset_context and asset_context.get("context_available"))

    direct = list(safety_result.get("direct_hazards", []))
    service = list(safety_result.get("service_hazards", []))
    immediate = bool(safety_result.get("immediate_danger"))
    required_depts = list(safety_result.get("required_departments", []))
    if immediate and not required_depts:
        required_depts = [hazard_depts.get("unknown_immediate_danger", "emergency_control_room")]

    pred_sla = sla_table.get(pred) if pred else None
    pred_is_critical = pred_sla is not None and pred_sla <= critical_threshold
    hazard_implied_critical = any(
        (sla_table.get(d) is not None and sla_table.get(d) <= critical_threshold) for d in required_depts
    ) or immediate
    infra_depts = set(policy.get("asset_context_required_for", []))
    infra_related = (pred in infra_depts) or any(d in infra_depts for d in required_depts)

    red: list[tuple[str, str]] = []
    yellow: list[tuple[str, str]] = []
    missing: list[str] = []

    # ---- mandatory Red overrides -------------------------------------------------------
    if immediate:
        red.append(("STRUCTURED_IMMEDIATE_DANGER", ""))
    if direct:
        red.append(("DIRECT_HAZARD", ", ".join(direct)))
    if direct and hazard_implied_critical and not pred_is_critical:
        red.append(("DANGEROUS_DOWNGRADE", f"{', '.join(direct)} -> {pred or 'unparseable'}"))
    if (direct or immediate) and tier == "very_high":
        red.append(("VERY_HIGH_ASSET_CRITICALITY", _tier_detail(asset_context)))
    if proposed_sla is not None and window is not None and proposed_sla >= window and (direct or immediate or tier in ("high", "very_high")):
        red.append(("REPAIR_WINDOW_AT_RISK", f"{proposed_sla:g} h proposed vs {window:g} h assumed failure window"))
    if (direct or immediate) and reliability in ("degraded", "unavailable"):
        red.append(("RELIABILITY_DEGRADED" if reliability == "degraded" else "RELIABILITY_UNAVAILABLE", ""))

    # ---- Yellow conditions ---------------------------------------------------------------
    if not pred:
        yellow.append(("UNPARSEABLE_CLASSIFICATION", ""))
    if margin is None:
        missing.append("prediction_margin")
        yellow.append(("MISSING_REQUIRED_FIELD", "prediction_margin"))
    elif margin < policy["uncertainty"]["low_margin_threshold"]:
        yellow.append(("LOW_MARGIN", f"margin {margin:g}"))
    if not complete:
        yellow.append(("TRUNCATED_CLASSIFIER_INPUT", ""))
    if infra_related and not ctx_ok:
        missing.append("asset_context")
        yellow.append(("ASSET_CONTEXT_MISSING", (asset_context or {}).get("reason") or "no mapping"))
    if reliability == "degraded":
        yellow.append(("RELIABILITY_DEGRADED", ""))
    elif reliability != "normal":
        yellow.append(("RELIABILITY_UNAVAILABLE", ""))
    conflicts = [d for d in ({hazard_depts.get(h) for h in service} - {None}) if pred and d != pred]
    if conflicts:
        yellow.append(("CONFLICTING_SIGNALS", f"{', '.join(service)} vs {pred}"))
    if infra_related and ctx_ok and tier == "very_high" and not red:
        yellow.append(("VERY_HIGH_ASSET_CRITICALITY", _tier_detail(asset_context)))
    if infra_related and ctx_ok and tier == "high":
        yellow.append(("HIGH_ASSET_CRITICALITY", _tier_detail(asset_context)))
    if proposed_sla is not None and window is not None and proposed_sla >= window and not red:
        yellow.append(("REPAIR_WINDOW_AT_RISK", f"{proposed_sla:g} h proposed vs {window:g} h assumed failure window"))
    for field in ("original_text", "language"):
        if not firewall_input.get(field):
            missing.append(field)
            yellow.append(("MISSING_REQUIRED_FIELD", field))

    # ---- decide ---------------------------------------------------------------------------
    if red:
        level, action = "red", "emergency_dispatch"
        final_dept = required_depts[0] if required_depts else hazard_depts.get("unknown_immediate_danger", "emergency_control_room")
        codes = red + [c for c in yellow if c[0] not in {r[0] for r in red}]
    elif yellow:
        level, action = "yellow", "human_verification"
        final_dept = pred or "verification"
        codes = yellow
    else:
        level, action = "green", "automatic_route"
        final_dept = pred
        codes = [("SAFE_AUTOMATION_ALLOWED", "")]

    # de-duplicate while preserving order
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for code, detail in codes:
        if code not in seen:
            seen.add(code)
            ordered.append((code, detail))

    return {
        "risk_level": level,
        "action": action,
        "final_department": final_dept,
        "recommended_department": pred or None,
        "ai_autonomy_allowed": level == "green",
        "human_review_required": level != "green",
        "dispatch_immediate": level == "red",
        "ai_route_overridden": level == "red" and final_dept != pred,
        "reason_codes": [c for c, _ in ordered],
        "reason_text": [_reason_text(c, d) for c, d in ordered],
        "missing_fields": sorted(set(missing)),
        "signals": {
            "direct_hazards": direct,
            "service_hazards": service,
            "immediate_danger": immediate,
            "predicted_dept": pred or None,
            "prediction_margin": margin,
            "classifier_input_complete": complete,
            "reliability_state": reliability,
            "criticality_tier": tier,
            "proposed_sla_hours": proposed_sla,
            "scenario_failure_window_hours": window,
        },
        "provenance": {
            "policy_thresholds": "assumed prototype policy (config.yaml: firewall)",
            "safety_scan": safety_result.get("provenance", {}).get("text_scan", "measured_rule_based"),
            "asset_context": (asset_context or {}).get("provenance", {}).get("asset_mapping", "no mapping"),
            "consequence": "simulated (corrected cascade engine)",
            "reliability_state": "policy response to a supplied controlled-canary signal, not production monitoring",
        },
    }


def _tier_detail(ctx: dict[str, Any] | None) -> str:
    if not ctx or not ctx.get("context_available"):
        return "unknown"
    return (f"{ctx.get('asset_name') or ctx.get('asset_id')}: rank {ctx['criticality_rank']}/{ctx['n_ranked_assets']}, "
            f"percentile {ctx['criticality_percentile']:g}, simulated exposure {ctx['simulated_people_exposed']:,}")


def _reason_text(code: str, detail: str) -> str:
    template = REASON_TEXT.get(code, code)
    return template.replace("({detail})", f"({detail})" if detail else "").replace("{detail}", detail).replace("  ", " ").strip()


# --------------------------------------------------------------------------- 5. action plan


def build_action_plan(decision: dict[str, Any], predicted_dept: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Convert the risk decision into a SIMULATED operational action plan. Nothing here sends a
    message, creates a real ticket or touches any municipal system."""
    ap = policy["action_policy"]
    level = decision["risk_level"]
    base = {
        "simulated": True,
        "risk_level": level,
        "ai_recommended_department": predicted_dept or None,
        "policy_provenance": "assumed prototype policy (config.yaml: firewall.action_policy)",
    }
    if level == "red":
        return {
            **base,
            "work_order_type": "emergency_work_order",
            "assigned_department": decision["final_department"],
            "priority": "P1_immediate",
            "requires_acknowledgement": True,
            "human_review_parallel": True,
            "status": "dispatched_awaiting_acknowledgement",
            "acknowledgement_target_minutes": ap["red_acknowledgement_target_minutes"],
            "reescalation_target_minutes": ap["red_reescalation_target_minutes"],
            "next_action_if_unacknowledged": f"re-escalate to {ap['red_escalation_target']}",
            "ai_route_finalized": False,
        }
    if level == "yellow":
        return {
            **base,
            "work_order_type": "human_verification_task",
            "assigned_department": "verification_desk",
            "priority": "P2_rapid_review",
            "requires_acknowledgement": True,
            "human_review_parallel": False,
            "status": "awaiting_human_verification",
            "review_target_hours": ap["yellow_review_target_hours"],
            "next_action_if_unacknowledged": f"re-escalate to {ap['red_escalation_target']} after {ap['yellow_review_target_hours']} h",
            "ai_route_finalized": False,
        }
    return {
        **base,
        "work_order_type": "routed_ticket",
        "assigned_department": decision["final_department"],
        "priority": "P3_normal",
        "requires_acknowledgement": False,
        "human_review_parallel": False,
        "status": "routed_automatically",
        "next_action_if_unacknowledged": "none (normal department queue)",
        "ai_route_finalized": True,
    }


def advance_acknowledgement(plan: dict[str, Any], acknowledged: bool, minutes_elapsed: float, policy: dict[str, Any]) -> dict[str, Any]:
    """Deterministic acknowledgement state machine for a simulated work order.

    Red: acknowledged -> ``acknowledged``; unacknowledged past the re-escalation target ->
    ``reescalated_to_control_room``; otherwise still ``dispatched_awaiting_acknowledgement``.
    Yellow: acknowledged -> ``verified_and_routed``; past the review target -> re-escalated.
    Green: untouched (no acknowledgement required).
    """
    ap = policy["action_policy"]
    out = dict(plan)
    out["minutes_elapsed"] = minutes_elapsed
    if not plan.get("requires_acknowledgement"):
        out["acknowledgement_state"] = "not_required"
        return out
    if acknowledged:
        out["status"] = "acknowledged" if plan["risk_level"] == "red" else "verified_and_routed"
        out["acknowledgement_state"] = "acknowledged"
        return out
    limit = ap["red_reescalation_target_minutes"] if plan["risk_level"] == "red" else ap["yellow_review_target_hours"] * 60
    if minutes_elapsed >= limit:
        out["status"] = f"reescalated_to_{ap['red_escalation_target']}"
        out["acknowledgement_state"] = "reescalated"
        out["escalated_to"] = ap["red_escalation_target"]
    else:
        out["acknowledgement_state"] = "awaiting"
    return out


# --------------------------------------------------------------------------- 6. orchestration


def classify_for_firewall(text: str, condition: str, config: dict[str, Any]) -> dict[str, Any]:
    """Run the controlled classifier exactly as the AI routing layer would and expose the
    uncertainty signal (score margin). The Firewall treats the result as advice only."""
    seen, keywords = condition_input(text, condition, config["d2"]["truncate_chars"])
    scores = classify_scores(seen, keywords)
    ranked = sorted(DEPARTMENTS, key=lambda d: (-scores[d], DEPARTMENTS.index(d)))
    top, second = ranked[0], ranked[1]
    predicted = top if scores[top] > 0 else ""
    return {
        "seen_text": seen,
        "input_complete": len(seen) >= len(text),
        "scores": scores,
        "predicted_dept": predicted,
        "margin": scores[top] - scores[second],
        "condition": condition,
        "vocabulary_size": sum(len(v) for v in keywords.values()),
    }


def run_firewall(
    complaint_id: str,
    original_text: str,
    language: str,
    condition: str,
    config: dict[str, Any],
    *,
    structured_hazards: list[str] | None = None,
    immediate_danger: bool = False,
    asset_context: dict[str, Any] | None = None,
    reliability_state: str = "unavailable",
    scenario_failure_window_hours: float | None = None,
) -> dict[str, Any]:
    """End-to-end decision for one complaint: classifier -> independent scan -> policy ->
    action plan. Returns the complete auditable trace. Never reads ground truth."""
    policy = config["firewall"]
    clf = classify_for_firewall(original_text, condition, config)
    safety = detect_safety_hazards(original_text, language, structured_hazards, immediate_danger, policy)
    ctx = asset_context or build_asset_context(None, None, None, config)
    firewall_input = {
        "complaint_id": complaint_id,
        "original_text": original_text,
        "language": language,
        "structured_hazards": list(structured_hazards or []),
        "immediate_danger": bool(immediate_danger),
        "predicted_dept": clf["predicted_dept"],
        "prediction_margin": clf["margin"],
        "classifier_input_complete": clf["input_complete"],
        "asset_id": ctx.get("asset_id"),
        "asset_criticality_percentile": ctx.get("criticality_percentile"),
        "simulated_people_exposed": ctx.get("simulated_people_exposed"),
        "dependent_hospitals": ctx.get("dependent_hospitals"),
        "dependent_water_assets": ctx.get("dependent_water_assets"),
        # the route the AI-only workflow would actually take (unparseable -> configured fallback queue)
        "proposed_route": clf["predicted_dept"] or policy.get("ai_only_fallback_queue", "electrical_maintenance"),
        "proposed_sla_hours": _sla(clf["predicted_dept"] or policy.get("ai_only_fallback_queue", "electrical_maintenance"), config),
        "scenario_failure_window_hours": scenario_failure_window_hours,
        "reliability_state": reliability_state,
    }
    decision = assess_risk(firewall_input, safety, ctx, policy, config)
    plan = build_action_plan(decision, clf["predicted_dept"], policy)
    response_hours = _response_hours(decision, plan, config)
    return {
        "complaint_id": complaint_id,
        "language": language,
        "condition": condition,
        "firewall_input": firewall_input,
        "classifier": clf,
        "safety_scan": safety,
        "asset_context": ctx,
        "decision": decision,
        "action_plan": plan,
        "response_hours": response_hours,
        "ai_only": {
            "department": firewall_input["proposed_route"],
            "department_note": "" if clf["predicted_dept"] else "unparseable -> general/maintenance queue (legacy behaviour)",
            "response_hours": firewall_input["proposed_sla_hours"],
        },
    }


def _response_hours(decision: dict[str, Any], plan: dict[str, Any], config: dict[str, Any]) -> float | None:
    """Assumed response time for the FINAL action under the declared model (labelled assumed).

    Red    -> the emergency response time.
    Yellow -> the review target plus the SLA of the route a verifier would most plausibly
              confirm, inferred from RUNTIME evidence only: a service hazard's implied
              department if one was detected, else the AI's suggested department, else the
              configured fallback queue. It must NOT assume the verifier always upgrades the
              case to the emergency route — for a complaint with no hazard the verifier simply
              confirms a slow queue, and assuming otherwise would understate the response time
              and overstate how often the Firewall beats the failure window.
    Green  -> the routed department's SLA.
    """
    fw = config["firewall"]
    level = decision["risk_level"]
    if level == "red":
        return float(fw.get("emergency_response_hours", config["d2"]["sla_hours"]["electrical_emergency"]))
    if level == "yellow":
        signals = decision.get("signals", {})
        hazard_depts = fw.get("hazard_departments", {})
        implied = [hazard_depts[h] for h in signals.get("service_hazards", []) if h in hazard_depts]
        route = implied[0] if implied else (signals.get("predicted_dept") or fw.get("ai_only_fallback_queue", "electrical_maintenance"))
        confirmed_sla = _sla(route, config)
        if confirmed_sla is None:
            return None
        return float(fw["action_policy"]["yellow_review_target_hours"]) + float(confirmed_sla)
    return _sla(decision["final_department"], config)
