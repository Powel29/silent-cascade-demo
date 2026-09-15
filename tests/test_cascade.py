"""Simulator invariants for the corrected cascade engine (CLAUDE.md section 13.4)."""

from __future__ import annotations

import copy

import pytest

from cascade import cascade, criticality_ranking, summarize_final
from conftest import make_graph


def _loads(G):
    return {n: d["load"] for n, d in G.nodes(data=True) if d["type"] == "substation"}


def test_caller_graph_is_not_mutated(chain_graph):
    before = copy.deepcopy(chain_graph)
    cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    assert _loads(chain_graph) == _loads(before)
    assert set(chain_graph.nodes) == set(before.nodes)


def test_failed_load_is_shed_exactly_once(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    # step 0: nothing shed yet, A's load is pending
    assert tl[0]["load_shed_this_step"] == 0
    assert tl[0]["pending_shed_load"] == pytest.approx(100)
    # step 1: A sheds its 100 to its only live neighbour B (B: 80 + 100 = 180 > 120 -> trips)
    assert tl[1]["load_shed_this_step"] == pytest.approx(100)
    assert "B" in tl[1]["failed_substations"]
    # step 2: B sheds its CURRENT load (180) once; C: 90 + 180 -> trips
    assert tl[2]["load_shed_this_step"] == pytest.approx(180)
    assert "C" in tl[2]["failed_substations"]
    # step 3: C has no live neighbour -> its load becomes unserved, not duplicated
    assert tl[3]["load_shed_this_step"] == pytest.approx(270)
    assert tl[3]["unserved_load"] == pytest.approx(270)
    # A, B and C each shed exactly once; a node that already transferred never sheds again
    shed_events = [s["load_shed_this_step"] for s in tl]
    assert sum(1 for s in shed_events if s > 0) == 3


def test_load_conservation_at_every_snapshot(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    total = tl[0]["total_initial_load"]
    assert total == pytest.approx(270)
    for snap in tl:
        assert snap["live_load"] + snap["unserved_load"] + snap["pending_shed_load"] == pytest.approx(total)
    # by the end everything is unserved: no live substation remains
    assert tl[-1]["live_load"] == pytest.approx(0)
    assert tl[-1]["unserved_load"] == pytest.approx(270)


def test_overload_trips_on_the_correct_step():
    # A (100) sheds to B and D equally (50 each). B has headroom 30 -> trips at step 1.
    # D has headroom 60 -> survives. B then sheds 140 to its only live neighbour E (headroom 100)
    # -> E trips at step 2.
    G = make_graph(
        subs={"A": (120, 100, 1), "B": (120, 90, 1), "D": (120, 60, 1), "E": (200, 100, 1)},
        grid=[("A", "B"), ("A", "D"), ("B", "E")],
    )
    tl = cascade(G, ["A"], max_steps=12, hours_per_step=2.0)
    assert tl[1]["failed_substations"] == {"A", "B"}
    assert tl[2]["failed_substations"] == {"A", "B", "E"}
    assert "D" not in tl[-1]["failed_substations"]
    # D received 50 from A and nothing else: 60 + 50 = 110 < 120 -> overloaded (>90%) but alive
    assert "D" in tl[-1]["overloaded"]


def test_no_substation_is_over_capacity_and_alive(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    for snap in tl:
        # "overloaded" is >90% capacity but alive; anything >100% must have tripped that step
        assert not (snap["overloaded"] & snap["failed_substations"])


def test_hospital_buffer_expires_on_the_correct_step(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    # H1 is fed by A: feeder lost at step 0 -> on_backup; 8 h buffer at 2 h/step -> outage at step 4
    assert "H1" in tl[0]["on_backup"]
    assert tl[0]["hospitals_on_generator"] == ["H1"]
    assert "H1" in tl[3]["on_backup"] and "H1" not in tl[3]["service_outage"]
    assert "H1" in tl[4]["service_outage"]
    assert tl[4]["hospitals_without_power"] == ["H1"]
    # H2 is fed by C: C trips at step 2 -> outage at step 6
    assert "H2" in tl[2]["on_backup"]
    assert "H2" in tl[6]["service_outage"]


def test_water_buffer_expires_on_the_correct_step(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    # P1 fed by B: B trips at step 1 -> buffered; 6 h buffer -> outage at step 4
    assert "P1" in tl[1]["on_backup"]
    assert tl[1]["wards_without_water"] == []
    assert "P1" not in tl[3]["service_outage"]
    assert tl[4]["wards_without_water"] == ["P1"]


def test_cascade_terminates_when_nothing_changes():
    G = make_graph(subs={"A": (120, 60, 1), "B": (200, 60, 1)}, grid=[("A", "B")])
    tl = cascade(G, ["A"], max_steps=50, hours_per_step=2.0)
    # step 1 sheds A's load into B (60+60=120 < 200: no trip); step 2 has no change -> stop
    assert tl[-1]["step"] == 2
    assert tl[-1]["failed_substations"] == {"A"}
    assert tl[-1]["load_shed_this_step"] == 0


def test_max_steps_caps_the_run(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=2, hours_per_step=2.0)
    assert tl[-1]["step"] == 2


def test_summary_counts_backup_and_outage_separately(chain_graph):
    tl = cascade(chain_graph, ["A"], max_steps=12, hours_per_step=2.0)
    s = summarize_final(tl)
    assert s["hospitals_feeder_lost"] == 2
    assert s["hospitals_without_power"] == 2
    assert s["hospitals_on_backup"] == 0
    assert s["pumps_without_water"] == 1
    assert s["people_affected"] == 6000
    assert s["substations_failed"] == 3


def test_criticality_ranking_is_deterministic(chain_graph):
    r1 = criticality_ranking(chain_graph, max_steps=12, hours_per_step=2.0, top_n=None)
    r2 = criticality_ranking(chain_graph, max_steps=12, hours_per_step=2.0, top_n=None)
    assert r1.equals(r2)
    assert list(r1.columns[:3]) == ["rank", "node_id", "name"]
    assert r1["rank"].tolist() == [1, 2, 3]
    assert r1.iloc[0]["criticality_percentile"] == 100
    # A brings the whole chain down (6000). C alone sheds 90 into B (80+90=170>120) which then
    # sheds into A (100+170>120): also 6000. Tie broken by node id -> A first.
    assert r1.iloc[0]["node_id"] == "A"


def test_unknown_initial_failure_raises(chain_graph):
    with pytest.raises(KeyError):
        cascade(chain_graph, ["nope"])
