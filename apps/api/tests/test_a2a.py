"""The Critic as an A2A agent: another agent reads its card, and puts claims and questions to it."""

import json

import httpx
import pytest
from agent_framework.a2a import A2AAgent
from fastapi.testclient import TestClient

from court.a2a_server import app, respond
from court.mcp_server import match_moments
from court.server import create_app


@pytest.fixture
async def critic():
    """Agent Framework's own A2A client, talking to the Critic's A2A server in process."""
    transport = httpx.ASGITransport(app=app("http://critic.test/"))
    async with httpx.AsyncClient(transport=transport, base_url="http://critic.test") as http:
        yield A2AAgent(url="http://critic.test/", http_client=http), http


async def test_the_card_says_who_the_critic_is_and_what_it_can_do(critic):
    _, http = critic
    card = (await http.get("/.well-known/agent-card.json")).json()
    assert card["name"].endswith("Critic")
    assert [s["id"] for s in card["skills"]] == ["verify-claim", "ask-the-match"]
    assert card["supportedInterfaces"][0]["url"] == "http://critic.test/"


async def test_an_agent_puts_a_claim_and_gets_the_verdict(critic):
    agent, _ = critic
    moment = next(m for m in match_moments(21)["moments"] if m["kind"] == "goal")
    minute = int(moment["minute"].split("'")[0].split("+")[0])
    claim = {
        "seed": 21,
        "minute": minute,
        "kind": "goal",
        "team": moment["team"],
        "text": "A goal.",
        "citations": moment["citations"],
    }
    verdict = json.loads((await agent.run(json.dumps(claim))).text)
    assert verdict["approved"] is True
    early = json.loads((await agent.run(json.dumps(claim | {"minute": minute - 1}))).text)
    assert early["approved"] is False
    assert {r["code"] for r in early["reasons"]} == {"future_event"}


async def test_an_agent_asks_the_match_and_gets_a_checked_answer(critic):
    agent, _ = critic
    question = {"seed": 21, "minute": 70, "question": "What's the score?"}
    answer = json.loads((await agent.run(json.dumps(question))).text)
    assert answer["status"] == "verified" and answer["text"].startswith("Saltmarsh Rovers 2")
    injured = json.loads(
        (await agent.run(json.dumps(question | {"question": "Is anyone injured?"}))).text
    )
    assert injured["status"] == "cannot"


async def test_anything_else_gets_the_contract_back():
    for text in ("hello", "[1, 2]", json.dumps({"seed": 21, "kind": "goal"})):
        reply = await respond(text)
        assert "error" in reply and set(reply["skills"]) == {"verify-claim", "ask-the-match"}


def test_the_studio_serves_the_critic_over_a2a(monkeypatch):
    monkeypatch.setenv("STUDIO_PUBLIC_URL", "https://studio.example/")
    with TestClient(create_app()) as client:
        card = client.get("/a2a/.well-known/agent-card.json").json()
    assert card["supportedInterfaces"][0]["url"] == "https://studio.example/a2a/"
