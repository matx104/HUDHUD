"""Synthetic match event schema: the contract between ingest and every agent.

Conventions
- The pitch is 105 x 68 metres. Coordinates are in the frame of the event's `team`:
  x = 0 is that team's own goal line, x = 105 is the goal line it attacks; y runs 0-68
  across the pitch. Renderers de-normalise with `period` and
  `MatchMeta.home_attacks_right_first`.
- `t` is the match clock in seconds. Period 2 starts at t = 2700, so first-half
  stoppage time (t > 2700 in period 1) overlaps the second half's clock exactly as a
  real match clock does. **`seq` is the ordering key, never `t`.**
- `id` is stable and citable. Every downstream claim points back to these ids.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
HALF_SECONDS = 2700.0

X = Annotated[float, Field(ge=0, le=PITCH_LENGTH)]
Y = Annotated[float, Field(ge=0, le=PITCH_WIDTH)]
Unit = Annotated[float, Field(ge=0, le=1)]


class Side(StrEnum):
    HOME = "home"
    AWAY = "away"

    def other(self) -> "Side":
        return Side.AWAY if self is Side.HOME else Side.HOME


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- match metadata ------------------------------------------------------------------


class Player(_Frozen):
    id: str
    name: str
    number: int = Field(ge=1, le=99)
    position: Literal["GK", "DF", "MF", "FW"]
    team: Side


class Team(_Frozen):
    side: Side
    name: str
    short_name: str = Field(min_length=3, max_length=3)
    color: str = Field(pattern=r"^#[0-9A-F]{6}$")
    formation: str


class MatchMeta(_Frozen):
    """First message of every stream. `synthetic` is a machine-readable promise."""

    type: Literal["match_meta"] = "match_meta"
    match_id: str
    seed: int
    generator_version: str
    competition: str
    home: Team
    away: Team
    players: tuple[Player, ...]
    home_attacks_right_first: bool
    synthetic: Literal[True] = True

    def team(self, side: Side) -> Team:
        return self.home if side is Side.HOME else self.away


# --- events --------------------------------------------------------------------------


class _EventBase(_Frozen):
    id: str = Field(pattern=r"^e\d{5}$")
    seq: int = Field(ge=0)
    t: float = Field(ge=0, description="Match clock in seconds")
    period: Literal[1, 2]


class _TeamEvent(_EventBase):
    team: Side
    possession: int = Field(ge=1, description="Possession sequence number")


class PeriodStart(_EventBase):
    type: Literal["period_start"] = "period_start"
    kickoff_team: Side


class PeriodEnd(_EventBase):
    type: Literal["period_end"] = "period_end"


class PassOutcome(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    INTERCEPTED = "intercepted"
    OUT = "out"


class Pass(_TeamEvent):
    type: Literal["pass"] = "pass"
    player_id: str
    recipient_id: str = Field(description="Intended recipient")
    x: X
    y: Y
    end_x: X
    end_y: Y
    outcome: PassOutcome
    height: Literal["ground", "low", "high"]
    cross: bool
    distance_m: float = Field(ge=0)
    ball_speed_kmh: float = Field(ge=0)
    difficulty: Unit = Field(description="Pre-pass difficulty: 1 - P(complete)")
    accuracy: Unit = Field(description="How close the ball arrived to the intended target")
    under_pressure: bool


class ShotOutcome(StrEnum):
    GOAL = "goal"
    SAVED = "saved"
    OFF_TARGET = "off_target"
    BLOCKED = "blocked"
    WOODWORK = "woodwork"


class Shot(_TeamEvent):
    type: Literal["shot"] = "shot"
    player_id: str
    x: X
    y: Y
    body_part: Literal["right_foot", "left_foot", "head"]
    situation: Literal["open_play", "set_piece", "penalty"]
    outcome: ShotOutcome
    shot_speed_kmh: float = Field(ge=0)
    under_pressure: bool
    assist_event_id: str | None = Field(default=None, description="Pass that set up the shot")


class Tackle(_TeamEvent):
    """`team` is the tackling side; coordinates are in the tackler's frame."""

    type: Literal["tackle"] = "tackle"
    player_id: str
    opponent_id: str
    x: X
    y: Y
    outcome: Literal["won", "lost", "foul"]


class PossessionChange(_TeamEvent):
    """Every possession begins with one of these; `team` is the side gaining the ball."""

    type: Literal["possession_change"] = "possession_change"
    reason: Literal[
        "kickoff", "interception", "tackle", "out_of_play", "goal_kick", "shot_end", "loose_ball"
    ]
    x: X
    y: Y
    cause_event_id: str | None = None


class Pressure(_TeamEvent):
    """`team` is the pressing side; coordinates are in the presser's frame."""

    type: Literal["pressure"] = "pressure"
    player_id: str
    target_player_id: str
    x: X
    y: Y
    duration_s: float = Field(ge=0)


MatchEvent = Annotated[
    Pass | Shot | Tackle | PossessionChange | Pressure | PeriodStart | PeriodEnd,
    Field(discriminator="type"),
]
StreamMessage = Annotated[
    MatchMeta | Pass | Shot | Tackle | PossessionChange | Pressure | PeriodStart | PeriodEnd,
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[MatchEvent] = TypeAdapter(MatchEvent)
STREAM_ADAPTER: TypeAdapter[StreamMessage] = TypeAdapter(StreamMessage)


def minute_label(t: float, period: int) -> str:
    """Broadcast-style minute: 23', 45+2', 90+4'. Minute N covers t in [(N-1)*60, N*60)."""
    regulation_end = HALF_SECONDS * period
    if t >= regulation_end:
        return f"{int(regulation_end // 60)}+{int((t - regulation_end) // 60) + 1}'"
    return f"{int(t // 60) + 1}'"
