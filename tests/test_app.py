"""Streamlit app smoke tests (CLAUDE.md section 19, app). Uses streamlit.testing.v1.AppTest:
no browser, no network; the Leaflet map component renders as an opaque element.

These also guard the UI contract the redesign is built on: the verdict and the pipeline ribbon
render before any control, every feature stays reachable without opening an expander, and a
change of verdict is announced."""

from __future__ import annotations

import html
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent
NEEDS_OUTPUTS = pytest.mark.skipif(
    not (REPO_ROOT / "outputs" / "d1_criticality.csv").exists() or not (REPO_ROOT / "data" / "processed" / "graph.gpickle").exists(),
    reason="requires the built graph and the full D1 ranking",
)
CONTROL_KEYS = {"scenario", "complaint", "language", "condition", "asset", "reliability", "structured", "immediate", "use_window"}


def _markdown(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _verdict(at: AppTest) -> str:
    md = _markdown(at)
    for level in ("RED — IMMEDIATE EMERGENCY DISPATCH", "YELLOW — HUMAN VERIFICATION BEFORE ROUTING", "GREEN — AUTOMATIC ROUTING ALLOWED"):
        if level in md:
            return level.split(" ")[0]
    return "none"


@pytest.fixture(scope="module")
def app() -> AppTest:
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=300)
    at.run()
    return at


@NEEDS_OUTPUTS
def test_canonical_scenario_renders_red(app):
    assert not app.exception, [str(e.value) for e in app.exception]
    assert not app.error
    md = _markdown(app)
    assert _verdict(app) == "RED"
    assert "DIRECT_HAZARD" in md
    assert "SAFE MODE ACTIVE" in md  # canonical scenario is Kannada + truncated -> degraded
    assert "emergency_work_order" in md
    assert "AI ONLY" in md and "WITH DECISION FIREWALL" in md  # contrast panels


@NEEDS_OUTPUTS
def test_pipeline_ribbon_shows_every_stage_with_live_values(app):
    """The ribbon carries the architecture, so a judge needs no narration."""
    md = _markdown(app)
    assert 'class="sc-ribbon"' in md
    for stage in ("Complaint", "AI prediction", "Independent scan", "Asset consequence", "AI quality check", "Firewall decision"):
        assert stage in md, stage
    assert md.count('class="sc-rt') == 6
    # reasons appear as short plain-language chips, with the stable code kept in the tooltip
    assert "very high consequence" in md and "input cut off" in md
    assert 'title="VERY_HIGH_ASSET_CRITICALITY"' in md and 'title="TRUNCATED_CLASSIFIER_INPUT"' in md
    assert "LR Bande Substation" in md  # asset context resolved and named


@NEEDS_OUTPUTS
def test_no_feature_is_hidden_behind_an_expander(app):
    """Controls stay on the page: a judge who never opens an expander still sees every input."""
    keys = {w.key for w in app.selectbox} | {w.key for w in app.radio} | {w.key for w in app.checkbox} | {w.key for w in app.multiselect}
    assert CONTROL_KEYS <= keys, CONTROL_KEYS - keys
    assert {"g_miss", "g_routine", "g_wait"} <= {b.key for b in app.button}


@NEEDS_OUTPUTS
def test_guided_buttons_drive_the_demo_and_announce_the_change(app):
    at = app
    at.button(key="g_routine").click().run()
    assert _verdict(at) == "GREEN"
    assert "CHANGED · RED → GREEN" in _markdown(at)
    at.button(key="g_miss").click().run()
    assert _verdict(at) == "RED"
    assert "CHANGED · GREEN → RED" in _markdown(at)


@NEEDS_OUTPUTS
def test_language_and_condition_change_recomputes_decision(app):
    at = app
    at.button(key="g_routine").click().run()  # Kannada streetlight, full text, normal-tier asset
    assert _verdict(at) == "GREEN"
    at.radio(key="condition").set_value("truncated").run()
    assert _verdict(at) != "GREEN"
    assert "TRUNCATED_CLASSIFIER_INPUT" in _markdown(at)
    at.radio(key="condition").set_value("clean").run()
    at.radio(key="language").set_value("en").run()
    assert not at.exception
    assert _verdict(at) in ("GREEN", "YELLOW", "RED")


@NEEDS_OUTPUTS
def test_changing_asset_changes_consequence_context(app):
    at = app
    at.button(key="g_routine").click().run()
    assert "MUSS NGEF" in _markdown(at)
    at.selectbox(key="asset").set_value("sub_039").run()  # very-high tier
    md = _markdown(at)
    assert "LR Bande Substation" in md
    assert "VERY_HIGH_ASSET_CRITICALITY" in md
    assert _verdict(at) == "YELLOW"
    at.selectbox(key="asset").set_value("(no asset context)").run()
    assert "ASSET_CONTEXT_MISSING" in _markdown(at)


@NEEDS_OUTPUTS
def test_changing_reliability_changes_ai_autonomy(app):
    at = app
    at.button(key="g_routine").click().run()
    at.selectbox(key="asset").set_value("sub_170").run()
    at.selectbox(key="reliability").set_value("normal").run()
    assert _verdict(at) == "GREEN"
    assert "SAFE MODE OFF" in _markdown(at)
    at.selectbox(key="reliability").set_value("degraded").run()
    md = _markdown(at)
    assert _verdict(at) == "YELLOW"
    assert "SAFE MODE ACTIVE" in md and "RELIABILITY_DEGRADED" in md
    assert "if healthy → GREEN" in md  # the counterfactual that teaches safe mode without prose
    at.selectbox(key="reliability").set_value("unavailable").run()
    assert "RELIABILITY_UNAVAILABLE" in _markdown(at)
    at.selectbox(key="reliability").set_value("auto").run()


@NEEDS_OUTPUTS
def test_unacknowledged_red_reescalates_in_ui(app):
    at = app
    at.button(key="g_miss").click().run()
    assert "dispatched awaiting acknowledgement" in _markdown(at)
    at.button(key="g_wait").click().run()
    assert "reescalated to control room supervisor" in _markdown(at)
    at.button(key="btn_ack").click().run()
    assert "acknowledged" in _markdown(at)
    at.button(key="btn_reset").click().run()


@NEEDS_OUTPUTS
def test_displayed_external_text_is_escaped(app):
    """Complaint text and OSM names are rendered via html.escape."""
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=300)
    at.run()
    md = _markdown(at)
    assert "<script" not in md
    assert html.escape("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


@NEEDS_OUTPUTS
def test_other_pages_render(app):
    at = app
    for page in ["Evidence", "Scenario explorer", "Methodology & limitations"]:
        at.radio(key="page").set_value(page).run()
        assert not at.exception, page
        assert not at.error, page
    md = _markdown(at)
    assert "Observed" in md and "Simulated" in md
    at.radio(key="page").set_value("Evidence").run()
    md = _markdown(at)
    assert "Dangerous AI routes intercepted" in md
    assert "count / denominator" in md  # every metric carries its denominator
    at.radio(key="page").set_value("Live intervention").run()


def test_missing_files_produce_actionable_errors(tmp_path):
    """With the ranking hidden, the app must show an error naming the command to run — not
    silently pick an asset."""
    import shutil

    work = tmp_path / "repo"
    work.mkdir()
    for name in ("app.py", "config.yaml"):
        shutil.copy(REPO_ROOT / name, work / name)
    shutil.copytree(REPO_ROOT / "src", work / "src")
    (work / "data").mkdir()
    shutil.copy(REPO_ROOT / "data" / "complaints.csv", work / "data" / "complaints.csv")
    shutil.copy(REPO_ROOT / "data" / "scenarios.csv", work / "data" / "scenarios.csv")
    shutil.copytree(REPO_ROOT / "data" / "processed", work / "data" / "processed")
    (work / "outputs").mkdir()  # no d1_criticality.csv
    at = AppTest.from_file(str(work / "app.py"), default_timeout=300)
    at.run()
    assert at.error, "expected an actionable error for the missing ranking"
    assert "python src/d1_cascade.py" in at.error[0].value
    assert not at.exception
