"""The Critic as an MCP server: outside claims meet the same evidence law as the broadcast's."""

import pytest
from fastapi.testclient import TestClient

from court.mcp_server import list_matches, match_events, match_moments, match_stats, verify_claim
from court.server import create_app


def _first_goal():
    moment = next(m for m in match_moments(21)["moments"] if m["kind"] == "goal")
    return moment, int(moment["minute"].rstrip("'"))


def test_the_matches_and_the_courts_own_claims_are_there_to_read():
    assert [m["seed"] for m in list_matches()["matches"]] == [21, 7, 33]
    moments = match_moments(21)["moments"]
    assert moments and all(m["approved"] for m in moments)


def test_a_true_claim_passes_and_says_how_many_numbers_were_checked():
    goal, minute = _first_goal()
    shot = next(
        e
        for e in match_events(21, minute, minute, kinds=["shot"])["events"]
        if e["outcome"] == "goal"
    )
    verdict = verify_claim(
        21, "goal", goal["team"], minute, f"A goal, xG {shot['xg']:.2f}.", goal["citations"]
    )
    assert verdict == {"approved": True, "as_of": f"{minute}'", "numbers_checked": 1, "reasons": []}


def test_a_caller_cant_vouch_for_its_own_numbers():
    goal, minute = _first_goal()
    verdict = verify_claim(21, "goal", goal["team"], minute, "From 30 m!", goal["citations"])
    assert [r["code"] for r in verdict["reasons"]] == ["ungrounded_number"]


def test_a_claim_about_what_hadnt_happened_yet_is_refused():
    goal, minute = _first_goal()
    verdict = verify_claim(21, "goal", goal["team"], minute - 1, "A goal.", goal["citations"])
    assert {r["code"] for r in verdict["reasons"]} == {"future_event"}


def test_stats_come_back_as_assertions_the_critic_recomputes():
    stats = match_stats(21, "home", 57, 62)["assertions"]
    done = next(a for a in stats if a["metric"] == "passes_completed")
    attacks = [
        e["id"]
        for e in match_events(21, 57, 62, team="home", limit=300)["events"]
        if e.get("into_final_third") or e["type"] == "shot"
    ][-10:]
    text = f"{done['value']:.0f} passes completed from 57' to 62'."
    assert verify_claim(21, "momentum_swing", "home", 62, text, attacks, [done])["approved"]
    inflated = dict(done, value=done["value"] + 5)
    text = f"{inflated['value']:.0f} passes completed from 57' to 62'."
    verdict = verify_claim(21, "momentum_swing", "home", 62, text, attacks, [inflated])
    assert [r["code"] for r in verdict["reasons"]] == ["assertion_mismatch"]


def test_bad_requests_are_refused_plainly():
    with pytest.raises(ValueError, match="no demo match"):
        match_stats(999, "home", 1, 10)
    with pytest.raises(ValueError, match="within one half"):
        match_stats(21, "home", 40, 50)


def test_the_studio_serves_the_critic_over_streamable_http(monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(create_app()) as client:
        hello = client.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert hello.status_code == 200 and hello.json()["result"]["serverInfo"]["name"].endswith(
            "critic"
        )
        tools = client.post(
            "/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        names = {t["name"] for t in tools.json()["result"]["tools"]}
        assert names == {
            "list_matches",
            "match_events",
            "match_stats",
            "match_moments",
            "verify_claim",
        }
