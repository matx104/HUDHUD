"""The match ledger: a match's history chained by hashes, verifiable by anyone, and a changed byte
anywhere shows."""

import copy
import hashlib
import itertools
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_server import _events

from court.ledger import (
    Ledger,
    check_proof,
    inclusion_path,
    leaf_hash,
    merkle_root,
    verify,
    verify_inclusion,
)
from court.server import create_app
from match_events import generate


@pytest.fixture(scope="module")
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        mp.delenv("COSMOS_ENDPOINT", raising=False)
        yield TestClient(create_app())


@pytest.fixture(scope="module")
def match(client):
    """One whole match from the studio, with its ledger as the page can download it."""
    events = _events(client, "seed=21&speed=0&stress=0.25")
    session = events[0][1]["session"]
    return events, session, client.get(f"/api/sessions/{session}/ledger").json()


def test_the_merkle_trees_are_certificate_transparencys():
    # RFC 6962: the empty tree is SHA-256 of nothing; a leaf is hashed under a 0x00 byte.
    assert merkle_root([]) == hashlib.sha256(b"").hexdigest()
    empty_leaf = "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d"
    assert merkle_root([leaf_hash("")]) == empty_leaf


@pytest.mark.parametrize("size", range(1, 34))
def test_every_entry_has_a_proof_and_a_changed_one_has_none(size):
    leaves = [leaf_hash(f"entry {i}") for i in range(size)]
    root = merkle_root(leaves)
    for index in range(size):
        path = inclusion_path(leaves, index)
        assert verify_inclusion(leaves[index], index, size, path, root)
        assert not verify_inclusion(leaf_hash("forged"), index, size, path, root)
        if size > 1:
            assert not verify_inclusion(leaves[index], (index + 1) % size, size, path, root)


def test_a_match_streams_its_blocks_and_ends_on_its_seal(match):
    events, _, exported = match
    blocks = [d for k, d in events if k == "block"]
    assert blocks[0]["height"] == 0 and blocks[0]["minute"] == "genesis"
    assert [b["height"] for b in blocks] == list(range(len(blocks)))
    assert all(b["prev"] == a["hash"] for a, b in itertools.pairwise(blocks))
    end = events[-1][1]
    assert end["ledger"]["seal"] == blocks[-1]["hash"] == exported["head"]
    assert end["ledger"]["blocks"] == len(blocks) > 90  # a block a minute, and full time
    # The page saw the same chain the file holds.
    assert [b["hash"] for b in exported["blocks"]] == [b["hash"] for b in blocks]
    kinds = {e["kind"] for b in exported["blocks"] for e in b["entries"]}
    assert {"meta", "event", "cue", "rejection", "recap"} <= kinds


def test_the_whole_ledger_verifies_and_its_events_are_the_seeds(match):
    _, _, exported = match
    check = verify(exported)
    assert check.ok, check.problems
    assert check.events_regenerated == 1815 and check.entries > 1815


def test_a_changed_line_breaks_its_block_and_every_one_after(match):
    _, _, exported = match
    forged = copy.deepcopy(exported)
    block = next(b for b in forged["blocks"] if any(e["kind"] == "cue" for e in b["entries"]))
    entry = next(e for e in block["entries"] if e["kind"] == "cue")
    cue = json.loads(entry["text"])
    cue["text"] = cue["text"] + " And it was the best goal ever."
    entry["text"] = json.dumps(cue, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    check = verify(forged, regenerate=False)
    assert not check.ok
    assert check.problems == [
        f"block {block['height']} ({block['minute']}): its entries don't match its root"
    ]
    # Re-sealing the forged block to hide it breaks the next block's link instead.
    block["root"] = merkle_root([leaf_hash(e["text"]) for e in block["entries"]])
    check = verify(forged, regenerate=False)
    assert any("its header doesn't match its hash" in p for p in check.problems)


def test_a_changed_event_is_not_the_one_the_seed_generates(match):
    _, _, exported = match
    forged = copy.deepcopy(exported)
    block = forged["blocks"][30]
    entry = next(e for e in block["entries"] if e["kind"] == "event")
    event = json.loads(entry["text"])
    event["t"] = event["t"] + 1
    entry["text"] = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    problems = verify(forged).problems
    assert any("isn't the event the seed generates" in p for p in problems)
    assert any("don't match its root" in p for p in problems)


def test_one_line_is_proved_in_a_few_hundred_bytes(client, match):
    events, session, _ = match
    cue = next(d for k, d in events if k == "output" and d["type"] == "cue")
    proof = client.get(f"/api/sessions/{session}/ledger/proof", params={"item": f"cue:{cue['id']}"})
    assert proof.status_code == 200
    proof = proof.json()
    assert check_proof(proof) and json.loads(proof["text"])["id"] == cue["id"]
    assert len(proof["path"]) <= 6
    forged = proof | {"text": proof["text"].replace(cue["headline"], "WORLD CLASS")}
    assert not check_proof(forged)
    missing = client.get(f"/api/sessions/{session}/ledger/proof", params={"item": "cue:nothing"})
    assert missing.status_code == 404


def test_after_full_time_each_answer_seals_a_block_of_its_own(client, match):
    _, session, before = match
    reply = client.post(f"/api/sessions/{session}/ask", json={"question": "Who scored?"}).json()
    after = client.get(f"/api/sessions/{session}/ledger").json()
    assert reply["ledger"]["block"] == len(after["blocks"]) - 1 == len(before["blocks"])
    # The chain goes on from the match's seal, and the reply names the new one.
    assert after["blocks"][-1]["prev"] == before["head"]
    assert reply["ledger"]["head"] == after["head"] != before["head"]
    assert verify(after).ok


SAMPLE = Path(__file__).parents[3] / "tests" / "studio" / "fixtures" / "ledger-sample.json"


def _sample() -> dict:
    """A small ledger with fixed times: the same bytes Python and the browser's code both check."""
    match = generate(21)
    at = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    ledger = Ledger(match.meta.model_dump(mode="json"), at=at)
    for event in match.events[:5]:
        ledger.add("event", event.id, event.model_dump(mode="json"))
    ledger.seal("1'", at=at)
    for event in match.events[5:12]:
        ledger.add("event", event.id, event.model_dump(mode="json"))
    # A line in Urdu: the canonical text keeps it as written, as JSON.stringify does.
    ledger.add("cue", "c1", {"id": "c1", "text": "سنہری موقع: Saltmarsh Rovers, xG 0.42", "n": 3})
    ledger.seal("2'", at=at)
    ledger.add("answer", "q1", {"id": "q1", "text": "Saltmarsh Rovers 1, Brackenfield 0."})
    ledger.seal("after full time: q1", at=at)
    return ledger.export()


def test_the_sample_both_languages_check_is_current_and_verifies():
    sample = _sample()
    if os.environ.get("UPDATE_FIXTURES"):
        SAMPLE.write_text(json.dumps(sample, ensure_ascii=False, indent=1) + "\n")
    assert json.loads(SAMPLE.read_text()) == sample, "UPDATE_FIXTURES=1 pytest writes it again"
    assert verify(sample).ok
