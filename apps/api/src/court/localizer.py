"""Localizer: the last mile. Language and audience depth are applied here.

Phase 1 renders English only. Urdu and Arabic arrive in Phase 3 and ship only after
owner review of every non-English string: never on the model's own instincts.
"""

from typing import Literal

from match_events import minute_label

from .contracts import Alert, AlertKind, Cue, Receipt, Verdict
from .state import MatchState

Mode = Literal["casual", "analyst"]
TTL_S = {AlertKind.GOAL: 12.0, AlertKind.BIG_CHANCE: 8.0, AlertKind.MOMENTUM_SWING: 10.0}


class Localizer:
    SUPPORTED_LANGS = ("en",)

    def __init__(self, *, lang: str = "en", mode: Mode = "casual") -> None:
        if lang not in self.SUPPORTED_LANGS:
            raise ValueError(f"language {lang!r} not supported yet: {self.SUPPORTED_LANGS}")
        self.lang = lang
        self.mode: Mode = mode

    def render(self, verdict: Verdict) -> Cue:
        """Approved claim -> broadcast cue."""
        claim = verdict.claim
        text = claim.text if self.mode == "analyst" else _first_sentence(claim.text)
        return Cue(
            id=f"q-{claim.id}",
            alert_id=claim.alert_id,
            kind=claim.kind,
            team=claim.team,
            period=claim.period,
            t=claim.t,
            minute=minute_label(claim.t, claim.period),
            headline=claim.headline,
            text=text,
            lang=self.lang,
            mode=self.mode,
            evidence=claim.citations,
            status="verified",
            attempts=claim.attempt,
            priority=claim.severity,
            ttl_s=TTL_S[claim.kind],
            # The checks; the Orchestrator adds the writer, its spend and the time.
            receipt=Receipt(
                attempts=claim.attempt,
                numbers_checked=verdict.numbers_checked,
                facts_recomputed=len(claim.assertions),
                evidence=len(claim.citations),
            ),
        )

    def detection_cue(self, alert: Alert, state: MatchState) -> Cue:
        """Degraded mode: the Scout's computed facts, no narrative. Still evidence-linked."""
        meta = state.meta
        team = meta.team(alert.team)
        m = alert.metrics
        if alert.kind is AlertKind.GOAL:
            home, away = m["home_goals"], m["away_goals"]
            headline = f"GOAL · {meta.home.short_name} {home:.0f}-{away:.0f} {meta.away.short_name}"
            text = f"Goal for {team.name} (xG {m['xg']:.2f})."
        elif alert.kind is AlertKind.BIG_CHANCE:
            headline = f"BIG CHANCE · {team.short_name}"
            text = f"Big chance for {team.name} (xG {m['xg']:.2f})."
        else:
            headline = f"MOMENTUM · {team.short_name} on top"
            mins = max(1, round(m["window_s"] / 60))
            text = f"{team.name}: {m['shots']:.0f} shots, {m['xg']:.2f} xG in {mins} min."
        return Cue(
            id=f"q-{alert.id}.d",
            alert_id=alert.id,
            kind=alert.kind,
            team=alert.team,
            period=alert.period,
            t=alert.t,
            minute=minute_label(alert.t, alert.period),
            headline=headline,
            text=text,
            lang=self.lang,
            mode=self.mode,
            evidence=alert.evidence,
            status="detection_only",
            attempts=0,
            priority=alert.severity,
            ttl_s=TTL_S[alert.kind],
            # No writer and no Critic: the Scout's own computed facts, cited.
            receipt=Receipt(writer="none", evidence=len(alert.evidence)),
        )


def _first_sentence(text: str) -> str:
    head, sep, _ = text.partition(". ")
    return head + "." if sep else text
