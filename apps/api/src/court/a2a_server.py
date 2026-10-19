"""The Critic as an A2A agent: any agent that speaks Agent2Agent can put a claim to it, or ask a
match a question, and get the Critic's verdict (ADR 0011).

The MCP server (ADR 0007) gives an assistant the Critic as tools. This gives another agent the
Critic as a peer: an Agent Framework agent, served by Agent Framework's A2AExecutor, with an agent
card that says what it does. There is no model inside: every reply is computed, so it is
read-only, deterministic and costs nothing, and an agent on the other side can't talk it round.

It has two skills, told apart by the JSON the message carries:

- verify-claim: {"seed", "minute", "kind", "team", "text", "citations", "assertions"}. The verdict,
  as court.mcp_server.verify_claim gives it: the same evidence law for every outside caller.
- ask-the-match: {"seed", "minute", "question"}. The answer from the offline answerer, through the
  Critic, with the facts it stands on (court.ask).

Anything else gets the contract back, so an agent can learn it from the first reply.

    the studio mounts it at /a2a/ (card: /a2a/.well-known/agent-card.json)
"""

import json
from typing import Any

from agent_framework import AgentResponse, BaseAgent, Message

from .ask import MatchTools, RuleAnswerer, ask
from .config import product_name
from .mcp_server import DEMO_SEEDS, _match, _state_at, verify_claim

CLAIM_KEYS = ("seed", "kind", "team", "minute", "text", "citations", "assertions")
CONTRACT = {
    "verify-claim": {
        "seed": "one of the demo matches",
        "minute": "1-90: the claim is judged as of the end of it",
        "kind": "goal | big_chance | momentum_swing | great_pass",
        "team": "home | away",
        "text": "the claim, in words",
        "citations": ["the event ids it rests on"],
        "assertions": [{"metric": "shots", "team": "home", "value": 7}],
    },
    "ask-the-match": {"seed": "one of the demo matches", "minute": "1-90", "question": "words"},
}


async def respond(text: str) -> dict[str, Any]:
    """The reply to one message: a verdict, an answer, or the contract."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        data = None
    if not isinstance(data, dict):
        return {"error": "send one JSON object, for one of the two skills", "skills": CONTRACT}
    try:
        if "question" in data:
            return await _ask(int(data["seed"]), int(data["minute"]), str(data["question"]))
        missing = [k for k in CLAIM_KEYS if k not in data and k != "assertions"]
        if missing:
            return {"error": f"a claim needs {', '.join(missing)}", "skills": CONTRACT}
        return verify_claim(**{k: data[k] for k in CLAIM_KEYS if k in data})
    except (KeyError, TypeError, ValueError) as error:
        return {"error": str(error), "skills": CONTRACT}


async def _ask(seed: int, minute: int, question: str) -> dict[str, Any]:
    if not 1 <= minute <= 90:
        raise ValueError("minute must be between 1 and 90")
    state = _state_at(_match(seed), minute)
    answer = await ask(question, MatchTools(state), RuleAnswerer())
    return answer.model_dump(mode="json")


class CriticAgent(BaseAgent):
    """The Critic, as an agent: a message in, the Critic's reply out, with no model between."""

    def __init__(self) -> None:
        super().__init__(
            name=f"{product_name()} Critic",
            description="Checks claims about synthetic football matches against their events, "
            "and answers questions about them from counts the Critic recomputes.",
        )

    async def run(self, messages=None, *, stream: bool = False, session=None, **_: Any):
        if stream:
            raise NotImplementedError("the Critic replies in one piece")
        reply = await respond(_text(messages))
        return AgentResponse(
            messages=[Message("assistant", [json.dumps(reply, ensure_ascii=False)])]
        )


def _text(messages: Any) -> str:
    """The last message's text, whatever shape the caller sent it in."""
    if isinstance(messages, str):
        return messages
    if isinstance(messages, Message):
        return messages.text
    if isinstance(messages, list | tuple) and messages:
        return _text(messages[-1])
    return ""


def card(url: str):
    """The agent card: who the Critic is, where to reach it, and its two skills."""
    from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
    from a2a.utils.constants import PROTOCOL_VERSION_CURRENT as PROTOCOL_VERSION

    matches = ", ".join(map(str, DEMO_SEEDS))
    return AgentCard(
        name=f"{product_name()} Critic",
        description="The adversarial verifier from an evidence-first football commentary system. "
        "Every number in a claim must be recomputed from the raw events or carried by an event "
        f"the claim cites; it refuses what it can't prove, and says why. Synthetic matches only "
        f"(seeds {matches}): every club and player is invented. No model inside: deterministic.",
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[
            AgentInterface(url=url, protocol_binding="JSONRPC", protocol_version=PROTOCOL_VERSION)
        ],
        skills=[
            AgentSkill(
                id="verify-claim",
                name="Verify a claim",
                description="Put a claim about a match to the Critic, as of the end of a "
                "minute: its citations, and an assertion for every number. Returns approved, or "
                "every reason it was refused.",
                tags=["football", "fact-checking", "evidence"],
                examples=[json.dumps(CONTRACT["verify-claim"])],
            ),
            AgentSkill(
                id="ask-the-match",
                name="Ask the match",
                description="A question about a match, answered from counts code made of the "
                "events up to a minute and checked by the Critic, with the facts it stands on; "
                "or, for what event data can't see, a plain statement that it can't answer.",
                tags=["football", "question-answering", "evidence"],
                examples=[json.dumps({"seed": 21, "minute": 70, "question": "Who scored?"})],
            ),
        ],
    )


def app(url: str):
    """The A2A server, as an ASGI app: the card, and JSON-RPC at the root."""
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
    from a2a.server.tasks import InMemoryTaskStore
    from agent_framework.a2a import A2AExecutor
    from starlette.applications import Starlette

    public = card(url)
    handler = DefaultRequestHandler(
        agent_executor=A2AExecutor(CriticAgent()),
        task_store=InMemoryTaskStore(),
        agent_card=public,
    )
    return Starlette(
        routes=[*create_agent_card_routes(public), *create_jsonrpc_routes(handler, "/")]
    )
