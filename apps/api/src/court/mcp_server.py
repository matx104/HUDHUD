"""The Critic as an MCP server: any assistant can have a football claim checked (ADR 0007).

GitHub Copilot, or any MCP client, can read a synthetic match and put a claim about it to the same
Critic that guards the broadcast. Every tool is read-only and deterministic: no model calls, no
keys, nothing written. The evidence law holds for outside callers too: a number in a claim must be
backed by an assertion the Critic recomputes from raw events, or carried by an event the claim
cites. A caller can't supply trusted figures of its own, so it can't vouch for its own numbers.

    .venv/bin/python -m court.mcp_server                 # stdio, for Copilot in VS Code
    https://<studio>/mcp/                                 # streamable HTTP, mounted on the studio
"""

from functools import lru_cache
from importlib.metadata import version
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from match_events import Pass, Shot, Side, SyntheticMatch, generate, minute_label

from .config import product_name
from .contracts import AlertKind, Assertion, Claim, Window
from .critic import Critic
from .describe import describe
from .metrics import compute, is_final_third_pass, shot_distance, shot_xg
from .narrator import TemplateNarrator
from .scout import Scout
from .state import MatchState
from .telemetry import tracer

DEMO_SEEDS = (21, 7, 33)
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
Kind = Literal["goal", "big_chance", "momentum_swing", "great_pass"]
Team = Literal["home", "away"]
METRICS = ("goals", "shots", "xg", "passes", "passes_completed", "final_third_passes")

server = MCPServer(
    name=f"{product_name().lower()}-critic",
    title=f"{product_name()} Critic",
    version=version("match-court"),
    instructions=(
        "Check claims about synthetic football matches against their raw events. Read a match "
        "with match_events and match_stats, then put a claim to verify_claim: cite the events it "
        "rests on, and back every number in the text with an assertion (match_stats returns them "
        "ready to use) or an event the claim cites. The Critic refuses anything it can't prove, "
        "and says why. Every club, player and match is invented."
    ),
)


@lru_cache(maxsize=8)
def _match(seed: int) -> SyntheticMatch:
    if seed not in DEMO_SEEDS:
        raise ValueError(f"no demo match with seed {seed}; list_matches shows them")
    return generate(seed)


def _period_of(minute: int) -> int:
    return 1 if minute <= 45 else 2


def _state_at(match: SyntheticMatch, minute: int) -> MatchState:
    """The match as it stood at the end of a minute: only what had happened by then."""
    period, state = _period_of(minute), MatchState(match.meta)
    for event in match.events:
        if event.period > period or (event.period == period and event.t >= minute * 60):
            break
        state.apply(event)
    return state


def _window(period: int, from_minute: int, to_minute: int) -> Window:
    return Window(period=period, start_t=(from_minute - 1) * 60.0, end_t=to_minute * 60.0 - 0.001)


def _event_figures(state: MatchState, citations: list[str]) -> dict[str, float]:
    """Numbers the cited events themselves carry, computed here, never taken from the caller."""
    figures: dict[str, float] = {}
    for event_id in citations:
        event = state.get(event_id)
        if isinstance(event, Shot):
            figures[f"{event_id}_xg"] = round(shot_xg(event), 2)
            figures[f"{event_id}_m"] = round(shot_distance(event))
            figures[f"{event_id}_kmh"] = round(event.shot_speed_kmh)
        elif isinstance(event, Pass):
            figures[f"{event_id}_m"] = round(event.distance_m)
            figures[f"{event_id}_kmh"] = round(event.ball_speed_kmh)
    return figures


def _traced(tool: str, seed: int, **attributes: Any):
    return tracer.start_as_current_span(
        f"mcp {tool}", attributes={"hudhud.mcp.tool": tool, "hudhud.seed": seed, **attributes}
    )


@server.tool(annotations=READ_ONLY)
def list_matches() -> dict[str, Any]:
    """The synthetic matches the Critic can check claims about, with their teams."""
    matches = []
    for seed in DEMO_SEEDS:
        meta = _match(seed).meta
        matches.append(
            {
                "seed": seed,
                "match_id": meta.match_id,
                "competition": meta.competition,
                "home": meta.home.name,
                "away": meta.away.name,
            }
        )
    return {"matches": matches, "note": "Every club, player and match is invented."}


@server.tool(annotations=READ_ONLY)
def match_events(
    seed: int,
    from_minute: int = 1,
    to_minute: int = 90,
    team: Team | None = None,
    kinds: list[Literal["shot", "pass", "tackle", "pressure"]] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """The raw events of a match between two minutes, with the ids a claim cites.

    Passes are many; ask for kinds=["shot"] or a short window to keep the list small.
    """
    with _traced("match_events", seed):
        match = _match(seed)
        state = MatchState(match.meta)
        found = []
        for event in match.events:
            state.apply(event)
            minute = int(minute_label(event.t, event.period).split("'")[0].split("+")[0])
            if not from_minute <= minute <= to_minute or event.type not in (kinds or (event.type,)):
                continue
            if team and getattr(event, "team", None) != Side(team):
                continue
            if event.type in ("period_start", "period_end", "possession_change"):
                continue
            row = {
                "id": event.id,
                "minute": minute_label(event.t, event.period),
                "type": event.type,
                "team": event.team.value,
                "what": describe(event, state),
            }
            if isinstance(event, Shot):
                row |= {"outcome": event.outcome.value, "xg": round(shot_xg(event), 2)}
            elif isinstance(event, Pass):
                row |= {
                    "outcome": event.outcome.value,
                    "into_final_third": is_final_third_pass(event),
                }
            found.append(row)
            if len(found) >= max(1, min(limit, 300)):
                break
        return {"seed": seed, "events": found, "truncated": len(found) >= limit}


@server.tool(annotations=READ_ONLY)
def match_stats(seed: int, team: Team, from_minute: int, to_minute: int) -> dict[str, Any]:
    """Statistics code computed for one side between two minutes of the same half, each returned
    as an assertion verify_claim accepts as it is."""
    with _traced("match_stats", seed):
        if _period_of(from_minute) != _period_of(to_minute) or from_minute > to_minute:
            raise ValueError("from_minute and to_minute must be in order, within one half")
        match, period = _match(seed), _period_of(to_minute)
        state = _state_at(match, to_minute)
        window = _window(period, from_minute, to_minute)
        events = list(state.in_window(window))
        side = Side(team)
        assertions = []
        for metric in METRICS:
            value = compute(metric, side, events)
            assertions.append(
                {
                    "metric": metric,
                    "team": team,
                    "value": round(value, 2),
                    "from_minute": from_minute,
                    "to_minute": to_minute,
                }
            )
        return {"seed": seed, "team": state.meta.team(side).name, "assertions": assertions}


@server.tool(annotations=READ_ONLY)
def match_moments(seed: int) -> dict[str, Any]:
    """The moments the court itself called in this match, and the verified claim it aired for
    each: worked examples of claims the Critic accepts."""
    with _traced("match_moments", seed):
        match = _match(seed)
        state, scout, narrator, critic = (
            MatchState(match.meta),
            Scout(),
            TemplateNarrator(),
            Critic(),
        )
        moments = []
        for event in match.events:
            state.apply(event)
            for alert in scout.observe(event, state):
                claim = narrator.draft(alert, state)
                verdict = critic.review(claim, state)
                moments.append(
                    {
                        "minute": minute_label(alert.t, alert.period),
                        "kind": alert.kind.value,
                        "team": alert.team.value,
                        "text": claim.text,
                        "citations": list(claim.citations),
                        "approved": verdict.approved,
                        "numbers_checked": verdict.numbers_checked,
                    }
                )
        return {"seed": seed, "moments": moments}


@server.tool(annotations=READ_ONLY)
def verify_claim(
    seed: int,
    kind: Kind,
    team: Team,
    minute: int,
    text: str,
    citations: list[str],
    assertions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Put a claim about a match to the Critic, as of the end of the given minute.

    citations: the event ids the claim rests on (match_events lists them). assertions: the
    numbers the claim relies on, as {metric, team, value, from_minute, to_minute}; metrics are
    goals, shots, xg, passes, passes_completed, final_third_passes, or one event's own with an
    event_id: shot_xg, shot_speed (km/h), pass_distance (m), pass_difficulty (0-100),
    pass_accuracy (%), ball_speed (km/h).
    Returns approved, and every reason if not, in the Critic's own words.
    """
    with _traced("verify_claim", seed, **{"hudhud.claim.kind": kind}) as span:
        if not 1 <= minute <= 90:
            raise ValueError("minute must be between 1 and 90")
        match, period = _match(seed), _period_of(minute)
        state = _state_at(match, minute)
        last = state.events[-1]
        parsed = []
        for a in assertions or []:
            window = None
            if "from_minute" in a and "to_minute" in a:
                window = _window(
                    _period_of(int(a["to_minute"])), int(a["from_minute"]), int(a["to_minute"])
                )
            parsed.append(
                Assertion(
                    metric=a["metric"],
                    team=Side(a.get("team", team)),
                    value=float(a["value"]),
                    window=window,
                    event_id=a.get("event_id"),
                )
            )
        figures = {"minute": float(minute), **_event_figures(state, citations)}
        for i, a in enumerate(assertions or []):  # the minutes that bound an assertion's window
            for edge in ("from_minute", "to_minute"):
                if edge in a:
                    figures[f"a{i}_{edge}"] = float(a[edge])
        claim = Claim(
            id="mcp.1",
            alert_id="mcp",
            attempt=1,
            kind=AlertKind(kind),
            team=Side(team),
            period=period,
            t=last.t,
            as_of_seq=last.seq,
            severity=0.5,
            headline=kind,
            text=text,
            citations=tuple(citations),
            assertions=tuple(parsed),
            figures=figures,
        )
        verdict = Critic().review(claim, state)
        codes = sorted({r.code.value for r in verdict.reasons})
        span.set_attributes(
            {"hudhud.mcp.approved": verdict.approved, "hudhud.rejection_codes": ",".join(codes)}
        )
        return {
            "approved": verdict.approved,
            "as_of": minute_label(last.t, last.period),
            "numbers_checked": verdict.numbers_checked,
            "reasons": [{"code": r.code.value, "detail": r.detail} for r in verdict.reasons],
        }


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
