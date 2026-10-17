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

    @property
    def approved(self) -> bool:
        return not self.reasons

    @property
    def rewritable(self) -> bool:
        return not any(r.code in UNFIXABLE for r in self.reasons)


# --- outputs: what leaves the system -------------------------------------------------


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
