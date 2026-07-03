"""The ground-truth is authored first and always recoverable: the oracle scores a perfect 1.0, events sit
on distinct hubs (so the hub-keyed maps never collapse), and answers are keyed by OBSERVATION-visible ids."""
from datagen import generate, observation_view, oracle_solve, score


def test_oracle_is_perfect():
    for d in (0.0, 0.6, 0.9):
        pkg = generate("logistics_demo", dirtiness=d, link_explicitness=4, seed="ho-3")
        truth = pkg["ground_truth"]["answers"]["explain_delays"]
        assert score(oracle_solve(pkg, "explain_delays"), truth)["f1"] == 1.0


def test_events_on_distinct_hubs():
    pkg = generate("logistics_demo", seed="ho-0")
    rhf = pkg["roles"]["record_hub_fk"]
    hubs = [ev[rhf] for ev in pkg["ground_truth"]["events"]]
    assert len(hubs) == len(set(hubs))  # one event per hub — no collapsed truths


def test_answers_keyed_by_observable_news_ids():
    pkg = generate("logistics_demo", seed="ho-0")
    news_ids = {n["id"] for n in pkg["stores"]["news"]}
    ans = pkg["ground_truth"]["answers"]["explain_delays"]
    assert ans and set(ans).issubset(news_ids)  # a solver that only sees the stores can be scored


def test_observation_view_hides_truth_metadata():
    pkg = generate("logistics_demo", seed="ho-0")
    obs = observation_view(pkg)
    # the internal truth-link tag must never leak into the observation channel
    assert all("_truth_event" not in n for n in obs["news"])
    assert "ground_truth" not in obs


def test_affected_shipments_match_events():
    pkg = generate("logistics_demo", seed="ho-5")
    rhf, rids = pkg["roles"]["record_hub_fk"], pkg["roles"]["record_ids_field"]
    for ev in pkg["ground_truth"]["events"]:
        # every shipment the event claims to delay must actually belong to that event's hub
        by_id = {s["id"]: s for s in pkg["stores"]["sql"]["shipments"]}
        for sid in ev[rids]:
            assert by_id[sid][rhf] == ev[rhf]
