"""Deterministic synthetic match generator.

Same seed, same stream, byte for byte: the demo must replay identically on camera.

The generator plays a possession-by-possession simulation. Hidden *momentum spells*
(stretches where one side is genuinely on top) tilt pass completion, territory and
shot propensity. Spells are returned as `GroundTruth` and never streamed, so the
Scout's detection can be scored against what really happened.
"""

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from .models import (
    HALF_SECONDS,
    PITCH_LENGTH,
    PITCH_WIDTH,
    MatchEvent,
    MatchMeta,
    Pass,
    PassOutcome,
    PeriodEnd,
    PeriodStart,
    Player,
    PossessionChange,
    Pressure,
    Shot,
    ShotOutcome,
    Side,
    StreamMessage,
    Tackle,
    Team,
)

GENERATOR_VERSION = "0.1.0"

# Invented clubs only: no real club names may appear in any output surface.
CLUBS: tuple[tuple[str, str, str], ...] = (
    ("Kestrel Vale", "KEV", "#2B6CB0"),
    ("Harrowmere Athletic", "HAR", "#C53030"),
    ("Saltmarsh Rovers", "SAL", "#2F855A"),
    ("Brackenfield", "BRK", "#6B46C1"),
    ("Ostwick Town", "OST", "#DD6B20"),
    ("Duneholt", "DUN", "#2D3748"),
    ("Corrin Bay", "COR", "#00838F"),
    ("Thornmoor", "THO", "#8D6E63"),
)
FIRST_NAMES = (
    "Aled", "Bram", "Cian", "Dario", "Emil", "Faris", "Goran", "Hugo", "Idris", "Jonah",
    "Kai", "Luka", "Mateo", "Niko", "Oskar", "Pavel", "Rafi", "Sami", "Teo", "Viktor",
    "Yusuf", "Zane", "Adem", "Bilal", "Caden", "Elio", "Ilyas", "Marek", "Tariq", "Omar",
)  # fmt: skip
SURNAME_HEADS = (
    "Ar", "Bel", "Cor", "Dun", "Esk", "Fal", "Gar", "Hal", "Ivr", "Jor", "Kel", "Lin",
    "Mor", "Nar", "Orv", "Pell", "Quin", "Ros", "Sten", "Tor", "Ulv", "Var", "Wex", "Yar",
)  # fmt: skip
SURNAME_TAILS = ("ston", "wick", "holm", "sen", "ley", "ford", "dal", "mere", "by", "ton", "vik")
FORMATION = ("GK", "DF", "DF", "DF", "DF", "MF", "MF", "MF", "FW", "FW", "FW")
SHIRTS = (1, 2, 5, 6, 3, 4, 8, 10, 7, 9, 11)

GOAL_Y = PITCH_WIDTH / 2
CENTRE = (PITCH_LENGTH / 2, GOAL_Y)


class MomentumSpell(BaseModel):
    model_config = ConfigDict(frozen=True)
    team: Side
    period: int
    start_t: float
    end_t: float
    strength: float


class GroundTruth(BaseModel):
    """What really happened. Never streamed to agents; used for evals only."""

    model_config = ConfigDict(frozen=True)
    spells: tuple[MomentumSpell, ...]
    final_score: dict[Side, int]
    styles: dict[Side, dict[str, float]]


@dataclass(frozen=True)
class SyntheticMatch:
    meta: MatchMeta
    events: tuple[MatchEvent, ...]
    truth: GroundTruth

    def stream(self) -> Iterator[StreamMessage]:
        yield self.meta
        yield from self.events


@dataclass(frozen=True)
class _Style:
    strength: float
    press: float
    directness: float


def _zone(x: float) -> str:
    return "DF" if x < 35 else "MF" if x < 70 else "FW"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _goal_angle(x: float, y: float) -> float:
    """Angle (radians) the goal mouth subtends from (x, y)."""
    dx, dy = PITCH_LENGTH - x, abs(GOAL_Y - y)
    angle = math.atan2(7.32 * dx, dx * dx + dy * dy - (7.32 / 2) ** 2)
    return angle + math.pi if angle < 0 else angle


def _true_xg(x: float, y: float, *, header: bool, pressured: bool) -> float:
    """The generator's hidden finishing model. The Scout uses its own, different model."""
    dist = math.hypot(PITCH_LENGTH - x, GOAL_Y - y)
    logit = -1.5 - 0.11 * dist + 1.5 * _goal_angle(x, y) - header * 1.1 - pressured * 0.3
    return 1 / (1 + math.exp(-logit))


class _Sim:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.seed = seed
        self.events: list[MatchEvent] = []
        self.seq = 0
        self.t = 0.0
        self.period: int = 1
        self.possession = 0
        self.score = {Side.HOME: 0, Side.AWAY: 0}
        self.att = Side.HOME
        self.x, self.y = CENTRE
        self.pressured = False
        self.set_piece = False
        self.last_pass: Pass | None = None

        rng = self.rng
        home_club, away_club = rng.sample(CLUBS, 2)
        self.styles = {
            side: _Style(
                strength=round(rng.uniform(0.42, 0.58), 3),
                press=round(rng.uniform(0.3, 0.8), 3),
                directness=round(rng.uniform(0.3, 0.7), 3),
            )
            for side in Side
        }
        self.teams = {
            Side.HOME: Team(
                side=Side.HOME,
                name=home_club[0],
                short_name=home_club[1],
                color=home_club[2],
                formation="4-3-3",
            ),
            Side.AWAY: Team(
                side=Side.AWAY,
                name=away_club[0],
                short_name=away_club[1],
                color=away_club[2],
                formation="4-3-3",
            ),
        }
        self.players = {side: self._squad(side) for side in Side}
        self.carrier = self.players[Side.HOME][9]
        self.spells = self._spells()

    # --- setup -------------------------------------------------------------------------

    def _squad(self, side: Side) -> list[Player]:
        used: set[str] = set()
        squad = []
        for i, (pos, shirt) in enumerate(zip(FORMATION, SHIRTS, strict=True)):
            while True:
                surname = self.rng.choice(SURNAME_HEADS) + self.rng.choice(SURNAME_TAILS)
                name = f"{self.rng.choice(FIRST_NAMES)} {surname}"
                if name not in used:
                    used.add(name)
                    break
            squad.append(
                Player(
                    id=f"{side.value[0]}{i + 1:02d}",
                    name=name,
                    number=shirt,
                    position=pos,
                    team=side,
                )
            )
        return squad

    def _spells(self) -> list[MomentumSpell]:
        spells = []
        for period in (1, 2):
            lo = 0.0 if period == 1 else HALF_SECONDS
            cursor = lo + self.rng.uniform(120, 600)
            for _ in range(self.rng.choice((1, 2, 2, 3))):
                length = self.rng.uniform(360, 840)
                if cursor + length > lo + HALF_SECONDS:
                    break
                spells.append(
                    MomentumSpell(
                        team=self.rng.choice((Side.HOME, Side.AWAY)),
                        period=period,
                        start_t=round(cursor, 1),
                        end_t=round(cursor + length, 1),
                        strength=round(self.rng.uniform(0.08, 0.18), 3),
                    )
                )
                cursor += length + self.rng.uniform(300, 900)
        return spells

    def _lift(self, side: Side) -> float:
        """Momentum tilt for `side` right now: own spells lift, opponent spells depress."""
        lift = 0.0
        for s in self.spells:
            if s.period == self.period and s.start_t <= self.t < s.end_t:
                lift += s.strength if s.team is side else -0.5 * s.strength
        return lift

    # --- primitives --------------------------------------------------------------------

    def _emit[E: MatchEvent](self, cls: type[E], **fields: object) -> E:
        event = cls(
            id=f"e{self.seq:05d}", seq=self.seq, t=round(self.t, 1), period=self.period, **fields
        )
        self.events.append(event)
        self.seq += 1
        return event

    def _pick(self, side: Side, position: str, exclude: Player | None = None) -> Player:
        pool = [p for p in self.players[side] if p.position == position and p is not exclude]
        if not pool:
            pool = [p for p in self.players[side] if p.position == "MF" and p is not exclude]
        return self.rng.choice(pool)

    def _new_possession(
        self, side: Side, reason: str, x: float, y: float, cause: str | None = None
    ) -> None:
        self.possession += 1
        self.att, self.x, self.y = side, x, y
        self.pressured = self.set_piece = False
        self.last_pass = None
        keeper = reason in ("goal_kick", "shot_end") and x < 8
        self.carrier = self.players[side][0] if keeper else self._pick(side, _zone(x))
        self._emit(
            PossessionChange,
            team=side,
            possession=self.possession,
            reason=reason,
            x=round(x, 1),
            y=round(y, 1),
            cause_event_id=cause,
        )

    # --- the match ---------------------------------------------------------------------

    def run(self) -> SyntheticMatch:
        first_kickoff = self.rng.choice((Side.HOME, Side.AWAY))
        home_right_first = self.rng.random() < 0.5
        for period, kickoff in ((1, first_kickoff), (2, first_kickoff.other())):
            self._play_period(period, kickoff)
        meta = MatchMeta(
            match_id=f"syn-{self.seed:06d}",
            seed=self.seed,
            generator_version=GENERATOR_VERSION,
            competition="Synthetic League",
            home=self.teams[Side.HOME],
            away=self.teams[Side.AWAY],
            players=tuple(self.players[Side.HOME] + self.players[Side.AWAY]),
            home_attacks_right_first=home_right_first,
        )
        truth = GroundTruth(
            spells=tuple(self.spells),
            final_score=dict(self.score),
            styles={s: vars(self.styles[s]) for s in Side},
        )
        return SyntheticMatch(meta=meta, events=tuple(self.events), truth=truth)

    def _play_period(self, period: int, kickoff: Side) -> None:
        self.period = period
        self.t = 0.0 if period == 1 else HALF_SECONDS
        stoppage = self.rng.uniform(60, 240) if period == 1 else self.rng.uniform(120, 360)
        end_t = HALF_SECONDS * period + stoppage
        self._emit(PeriodStart, kickoff_team=kickoff)
        self._new_possession(kickoff, "kickoff", *CENTRE)
        while self.t < end_t:
            self._step()
        self._emit(PeriodEnd)

    def _step(self) -> None:
        rng, att, dfn = self.rng, self.att, self.att.other()
        lift = self._lift(att)

        p_press = 0.12 + 0.22 * self.styles[dfn].press + 0.08 * (1 - self.x / PITCH_LENGTH)
        self.pressured = rng.random() < p_press
        if self.pressured:
            px, py = PITCH_LENGTH - self.x, PITCH_WIDTH - self.y
            self._emit(
                Pressure,
                team=dfn,
                possession=self.possession,
                player_id=self._pick(dfn, _zone(px)).id,
                target_player_id=self.carrier.id,
                x=round(px, 1),
                y=round(py, 1),
                duration_s=round(rng.uniform(0.8, 3.5), 1),
            )
            self.t += rng.uniform(0.5, 1.5)

        if rng.random() < 0.025 + 0.05 * self.pressured:
            self._tackle(att, dfn, lift)
        elif self._wants_shot(lift):
            self._shot(att, dfn, lift)
        else:
            self._pass(att, dfn, lift)

    def _wants_shot(self, lift: float) -> bool:
        dist = math.hypot(PITCH_LENGTH - self.x, GOAL_Y - self.y)
        if dist > 32:
            return False
        base = 0.26 if dist < 12 else 0.17 if dist < 18 else 0.08 if dist < 25 else 0.03
        return self.rng.random() < base * (1 + 2 * lift) * (0.7 if self.pressured else 1.0)

    def _pass(self, att: Side, dfn: Side, lift: float) -> None:
        rng, x, y = self.rng, self.x, self.y
        style = self.styles[att]
        cross = self.set_piece or (x > 80 and abs(y - GOAL_Y) > 18 and rng.random() < 0.35)
        if cross:
            end_x, end_y = rng.uniform(94, 100), rng.uniform(27, 41)
            height = "high"
        else:
            r = rng.random()
            if r < 0.68:
                length, height = rng.uniform(6, 20), "ground"
            elif r < 0.92:
                length, height = rng.uniform(20, 35), rng.choice(("ground", "low"))
            else:
                length, height = rng.uniform(35, 60), "high"
            sigma = 1.3 - 0.7 * style.directness - lift + (0.4 if x > 85 else 0.0)
            angle = rng.gauss(0, max(sigma, 0.35))
            end_x = x + length * math.cos(angle)
            end_y = y + length * math.sin(angle)
            if end_x > 99:
                end_x = rng.uniform(86, 99)
        out = not (0 <= end_y <= PITCH_WIDTH) and rng.random() < 0.25
        end_x, end_y = _clamp(end_x, 1, 104), _clamp(end_y, 0.5, PITCH_WIDTH - 0.5)
        distance = math.hypot(end_x - x, end_y - y)

        if cross:
            p = 0.28 + lift
        else:
            p = (
                0.97
                - 0.007 * max(0.0, distance - 12)
                - 0.10 * self.pressured
                - 0.08 * (end_x > 75)
                - 0.12 * (end_x > 88)
                + style.strength
                - self.styles[dfn].strength
                + lift
            )
        p = _clamp(p, 0.15, 0.97)
        complete = not out and rng.random() < p
        if complete:
            outcome = PassOutcome.COMPLETE
        elif out:
            outcome = PassOutcome.OUT
        else:
            outcome = PassOutcome.INTERCEPTED if rng.random() < 0.65 else PassOutcome.INCOMPLETE

        speed = (rng.uniform(28, 45) + distance * 0.9) * (1.15 if height == "high" else 1.0)
        recipient = self._pick(att, _zone(end_x), exclude=self.carrier)
        self.last_pass = self._emit(
            Pass,
            team=att,
            possession=self.possession,
            player_id=self.carrier.id,
            recipient_id=recipient.id,
            x=round(x, 1),
            y=round(y, 1),
            end_x=round(end_x, 1),
            end_y=round(end_y, 1),
            outcome=outcome,
            height=height,
            cross=cross,
            distance_m=round(distance, 1),
            ball_speed_kmh=round(speed, 1),
            difficulty=round(1 - p, 3),
            accuracy=round(rng.uniform(0.75, 1.0) if complete else rng.uniform(0.2, 0.7), 3),
            under_pressure=self.pressured,
        )
        self.t += distance / (speed / 3.6)
        was_set_piece, self.set_piece = self.set_piece, False

        if complete:
            self.carrier, self.x, self.y = recipient, end_x, end_y
            self.set_piece = was_set_piece  # a set-piece delivery keeps its label for the shot
            if rng.random() < 0.5:  # implicit carry
                reach = 8 if self.x < 85 else 3
                self.x = _clamp(self.x + rng.uniform(0, reach) * style.directness, 1, 99)
                self.t += rng.uniform(1, 3)
            self.t += rng.uniform(0.8, 2.8)
        elif out:
            self.t += rng.uniform(8, 25)
            if end_x > 103:
                self._new_possession(dfn, "goal_kick", 6, GOAL_Y, self.last_pass.id)
            else:
                self._new_possession(
                    dfn, "out_of_play", PITCH_LENGTH - end_x, PITCH_WIDTH - end_y, self.last_pass.id
                )
        else:
            self.t += rng.uniform(0.5, 1.5)
            reason = "interception" if outcome is PassOutcome.INTERCEPTED else "loose_ball"
            self._new_possession(
                dfn, reason, PITCH_LENGTH - end_x, PITCH_WIDTH - end_y, self.last_pass.id
            )

    def _shot(self, att: Side, dfn: Side, lift: float, *, penalty: bool = False) -> None:
        rng = self.rng
        lp = self.last_pass
        assisted = lp is not None and lp.outcome is PassOutcome.COMPLETE
        header = not penalty and assisted and lp.height == "high" and rng.random() < 0.7
        if penalty:
            self.x, self.y = 94.0, GOAL_Y
            xg = 0.76
        else:
            xg = _true_xg(self.x, self.y, header=header, pressured=self.pressured) * (1 + lift)
        if rng.random() < xg:
            outcome = ShotOutcome.GOAL
        else:
            outcome = rng.choices(
                (
                    ShotOutcome.SAVED,
                    ShotOutcome.OFF_TARGET,
                    ShotOutcome.BLOCKED,
                    ShotOutcome.WOODWORK,
                ),
                weights=(38, 37, 20, 5),
            )[0]
        situation = "penalty" if penalty else "set_piece" if self.set_piece else "open_play"
        shot = self._emit(
            Shot,
            team=att,
            possession=self.possession,
            player_id=self.carrier.id,
            x=round(self.x, 1),
            y=round(self.y, 1),
            body_part="head" if header else rng.choice(("right_foot", "right_foot", "left_foot")),
            situation=situation,
            outcome=outcome,
            shot_speed_kmh=round(rng.uniform(45, 75) if header else rng.uniform(70, 125), 1),
            under_pressure=self.pressured and not penalty,
            assist_event_id=lp.id if assisted and not penalty else None,
        )
        self.t += rng.uniform(1, 3)

        if outcome is ShotOutcome.GOAL:
            self.score[att] += 1
            self.t += rng.uniform(50, 90)
            self._new_possession(dfn, "kickoff", *CENTRE, shot.id)
        elif outcome in (ShotOutcome.SAVED, ShotOutcome.BLOCKED) and rng.random() < 0.3:
            self._corner(att)
        elif outcome is ShotOutcome.BLOCKED:
            self._new_possession(
                dfn,
                "loose_ball",
                _clamp(PITCH_LENGTH - self.x + 3, 1, 104),
                PITCH_WIDTH - self.y,
                shot.id,
            )
        elif outcome is ShotOutcome.SAVED:
            self._new_possession(dfn, "shot_end", 5, GOAL_Y, shot.id)
        else:
            self.t += rng.uniform(20, 35)
            self._new_possession(dfn, "goal_kick", 6, GOAL_Y, shot.id)

    def _corner(self, att: Side) -> None:
        self.t += self.rng.uniform(25, 40)
        self.x, self.y = 104.5, self.rng.choice((0.5, PITCH_WIDTH - 0.5))
        self.carrier = self._pick(att, "MF")
        self.set_piece, self.pressured, self.last_pass = True, False, None

    def _tackle(self, att: Side, dfn: Side, lift: float) -> None:
        rng = self.rng
        tx, ty = PITCH_LENGTH - self.x, PITCH_WIDTH - self.y
        p_foul = 0.12
        edge = self.styles[dfn].strength - self.styles[att].strength
        p_won = _clamp(0.55 + edge - lift, 0.3, 0.8)
        r = rng.random()
        outcome = "foul" if r < p_foul else "won" if r < p_foul + p_won * (1 - p_foul) else "lost"
        tackle = self._emit(
            Tackle,
            team=dfn,
            possession=self.possession,
            player_id=self._pick(dfn, _zone(tx)).id,
            opponent_id=self.carrier.id,
            x=round(tx, 1),
            y=round(ty, 1),
            outcome=outcome,
        )
        if outcome == "won":
            self.t += rng.uniform(1, 2)
            self._new_possession(dfn, "tackle", tx, ty, tackle.id)
        elif outcome == "lost":
            self.x = _clamp(self.x + rng.uniform(3, 10 if self.x < 85 else 4), 1, 99)
            self.t += rng.uniform(2, 3)
        else:
            self.t += rng.uniform(15, 40)
            in_box = self.x > 88.5 and 13.84 < self.y < 54.16
            if in_box:
                self._shot(att, dfn, lift, penalty=True)
            else:
                self.pressured, self.set_piece = False, self.x > 70


def generate(seed: int) -> SyntheticMatch:
    """Generate one full synthetic match. Pure function of `seed`."""
    return _Sim(seed).run()
