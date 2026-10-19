"""Handoff contracts between agents.

Flow: Scout --Alert--> Narrator --Claim--> Critic --Verdict--> Localizer --Cue--> air.
Anything that can reach air carries the event ids that justify it.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from match_events import Side


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AlertKind(StrEnum):
    GOAL = "goal"
    BIG_CHANCE = "big_chance"
    MOMENTUM_SWING = "momentum_swing"
    GREAT_PASS = "great_pass"
    RECAP = "recap"  # a line of the post-match recap (court.recap), never a live alert


class Window(_Frozen):
    """A stretch of match clock inside one period."""

    period: int
    start_t: float
    end_t: float


class Alert(_Frozen):
    """Scout -> Narrator. Computed from events, so it carries its own evidence."""

    id: str
    kind: AlertKind
    team: Side
    period: int
    t: float
    as_of_seq: int = Field(description="Last event the Scout had seen")
    severity: float = Field(ge=0, le=1)
    evidence: tuple[str, ...]
    metrics: dict[str, float]
    window: Window | None = None


Metric = Literal[
    "goals",
    "shots",
    "xg",
    "box_entries",
    "shot_xg",
    "passes",
    "passes_completed",
    "final_third_passes",
    # Per-event metrics (the assertion names its event_id), all as broadcast integers:
    "shot_speed",  # km/h
    "pass_distance",  # metres
    "pass_difficulty",  # 0-100: 100 x (1 - the chance the pass is completed)
    "pass_accuracy",  # percent: how close the ball arrived to its target
    "ball_speed",  # km/h
]


class Assertion(_Frozen):
    """A numeric fact a claim relies on. The Critic recomputes it from raw events."""

    metric: Metric
    team: Side
    value: float
    window: Window | None = Field(default=None, description="None = whole match so far")
    event_id: str | None = Field(default=None, description="For per-event metrics (shot_xg)")


class Claim(_Frozen):
    """Narrator -> Critic. Prose plus the machine-checkable chain behind it."""

    id: str
    alert_id: str
    attempt: int = Field(ge=1)
    kind: AlertKind
    team: Side
    period: int
    t: float
    as_of_seq: int
    severity: float = Field(ge=0, le=1)
    headline: str
    text: str
    citations: tuple[str, ...]
    assertions: tuple[Assertion, ...] = ()
    figures: dict[str, float] = Field(
        default_factory=dict,
        description="Numbers the text may state, computed by code from events; the Critic "
        "rejects any number in the text that is neither here nor in an assertion",
    )


class RejectionCode(StrEnum):
    NO_EVIDENCE = "no_evidence"
    UNKNOWN_EVENT = "unknown_event"
    FUTURE_EVENT = "future_event"
    STALE_EVENT = "stale_event"
    ASSERTION_MISMATCH = "assertion_mismatch"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNGROUNDED_NUMBER = "ungrounded_number"
    NO_RULE = "no_rule"


# A rewrite cannot fix these: the problem is the Critic's rulebook, not the prose.
UNFIXABLE = frozenset({RejectionCode.NO_RULE})


class Reason(_Frozen):
    code: RejectionCode
    detail: str


class Verdict(_Frozen):
    claim: Claim
    reasons: tuple[Reason, ...]
    numbers_checked: int = Field(
        default=0, description="Numbers in the text matched to figures or recomputed assertions"
    )

    @property
    def approved(self) -> bool:
        return not self.reasons

    @property
    def rewritable(self) -> bool:
        return not any(r.code in UNFIXABLE for r in self.reasons)


# --- outputs: what leaves the system -------------------------------------------------


class Receipt(_Frozen):
    """How a cue got on air: who wrote it, what was checked, and what it cost.

    Each part comes from the agent that knows it: the checks from the Critic's verdict, the
    writer and its spend from the narrator, the time from the Orchestrator. Nothing is estimated
    from the outside except cost, which is tokens at list prices.
    """

    writer: str = Field(
        default="unknown",
        description="The model that wrote the line, 'template', or 'none' for detection-only cues",
    )
    attempts: int = 0
    numbers_checked: int = Field(default=0, description="Numbers in the line the Critic matched")
    facts_recomputed: int = Field(default=0, description="Assertions recomputed from raw events")
    evidence: int = Field(default=0, description="Events cited")
    model_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    handovers: int = Field(default=0, description="Times a backup model took over for this cue")
    latency_ms: float = Field(default=0.0, description="From the alert to the cue")
    translated_by: str = Field(default="", description="The model that translated the line, if any")
    translation_refused: bool = Field(
        default=False, description="The translation stated a number the line doesn't: English aired"
    )


class PlayerTag(_Frozen):
    """A player the cue is about, for on-screen identification, with threshold badges (§4.1)."""

    id: str
    name: str
    number: int
    position: str
    team: Side
    role: Literal["scorer", "shooter", "assister", "passer", "involved"]
    badges: tuple[str, ...] = Field(
        default=(), description="Speed and distance tags, shown when a threshold is reached"
    )


# One number a viewer can follow all match in single-metric mode (court.personal).
TickerMetric = Literal[
    "xg", "shots", "box_entries", "final_third_passes", "passes_completed", "pass_completion"
]


class Preferences(_Frozen):
    """One viewer's way into the match (§4.1 i e: personal modes). It changes what airs first,
    what is marked as theirs and from whose side a line is told, never what is true: every line
    still passed the Critic, and every number on screen is computed from events."""

    club: Side | None = Field(default=None, description="Favourite club")
    player: str | None = Field(default=None, description="Favourite player, by id")
    focus: Literal["match", "player"] = Field(
        default="match", description="'player': only the favourite player's moments, and a card"
    )
    metric: TickerMetric | None = Field(default=None, description="Single-metric mode")


class Cue(_Frozen):
    """Broadcast overlay cue: timed, machine-readable, evidence attached."""

    type: Literal["cue"] = "cue"
    id: str
    alert_id: str
    kind: AlertKind
    team: Side
    period: int
    t: float
    minute: str
    headline: str
    text: str
    lang: str
    mode: Literal["casual", "analyst"]
    evidence: tuple[str, ...]
    status: Literal["verified", "detection_only"]
    attempts: int
    priority: float
    ttl_s: float
    receipt: Receipt | None = None
    players: tuple[PlayerTag, ...] = ()
    original: str | None = Field(
        default=None, description="The verified English line, when the text is its translation"
    )
    for_you: tuple[Literal["club", "rival", "player"], ...] = Field(
        default=(), description="Why this cue is the viewer's own (court.personal)"
    )


class RejectionNotice(_Frozen):
    """A claim the Critic refused. A first-class output the studio UI shows."""

    type: Literal["rejection"] = "rejection"
    minute: str
    claim: Claim
    reasons: tuple[Reason, ...]


class Spiked(_Frozen):
    """A story killed after the rewrite budget ran out, or with an unfixable reason."""

    type: Literal["spiked"] = "spiked"
    minute: str
    claim: Claim
    reasons: tuple[Reason, ...]


class Degradation(_Frozen):
    """The broadcast changed service level, and says so."""

    type: Literal["degradation"] = "degradation"
    level: Literal["full", "detection_only"]
    period: int
    t: float
    minute: str
    detail: str


Output = Annotated[Cue | RejectionNotice | Spiked | Degradation, Field(discriminator="type")]
OUTPUT_ADAPTER: TypeAdapter[Output] = TypeAdapter(Output)
