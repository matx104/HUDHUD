"""Localizer: the last mile. Language and audience depth are applied here.

Urdu and Arabic (ADR 0009): the Localizer translates the line the Critic has already verified,
with a model, under the same law as the Narrator. A translation may state no number the verified
line doesn't (critic.invented_numbers); one that does goes back once with the reason, and if it
still does, the English line airs and the receipt says the translation was refused. Names stay as
the verified line spells them, in Latin letters, so each can still be checked against the match.
Without a model, the line stays in English under its translated headline. The headline words
below are the only fixed non-English strings; the owner reviewed them and the live translations
and signed both off for production on 2026-10-18 (docs/review/ur-ar.md).
"""

from collections.abc import Awaitable, Callable
from typing import Literal

from match_events import MatchMeta, minute_label

from .contracts import Alert, AlertKind, Cue, Receipt, Verdict
from .critic import invented_numbers
from .state import MatchState

Mode = Literal["casual", "analyst"]
TTL_S = {
    AlertKind.GOAL: 12.0,
    AlertKind.BIG_CHANCE: 8.0,
    AlertKind.MOMENTUM_SWING: 10.0,
    AlertKind.GREAT_PASS: 8.0,
}


# The headline's label in each language, replacing the English one before " · ". Signed off by the
# owner for production, 2026-10-18 (docs/review/ur-ar.md): change them only with the owner.
LABELS = {
    "ur": {
        "GOAL": "گول",
        "BIG CHANCE": "سنہری موقع",
        "MOMENTUM": "میچ پر گرفت",
        "GREAT PASS": "شاندار پاس",
    },
    "ar": {
        "GOAL": "هدف",
        "BIG CHANCE": "فرصة خطيرة",
        "MOMENTUM": "السيطرة",
        "GREAT PASS": "تمريرة رائعة",
    },
}
ON_TOP = {"ur": "حاوی", "ar": "يسيطر"}

# A translator takes (alert id, the verified line, the language, reasons from a refused try) and
# returns (the translation, the model that wrote it).
Translator = Callable[[str, str, str, list[str]], Awaitable[tuple[str, str]]]


def local_headline(headline: str, lang: str) -> str:
    """'MOMENTUM · SAL on top' -> 'میچ پر گرفت · SAL حاوی'. Codes and scores stay as they are."""
    if lang == "en":
        return headline
    label, _, rest = headline.partition(" · ")
    rest = rest.replace(" on top", f" {ON_TOP[lang]}")
    return f"{LABELS[lang].get(label, label)} · {rest}" if rest else LABELS[lang].get(label, label)


class Localizer:
    SUPPORTED_LANGS = ("en", "ur", "ar")

    def __init__(
        self, *, lang: str = "en", mode: Mode = "casual", translator: Translator | None = None
    ) -> None:
        if lang not in self.SUPPORTED_LANGS:
            raise ValueError(f"language {lang!r} not supported yet: {self.SUPPORTED_LANGS}")
        self.lang = lang
        self.mode: Mode = mode
        self.translator = translator
        self.names: frozenset[str] = frozenset()

    def bind(self, meta: MatchMeta) -> None:
        """The match's player and team names: a translation must keep each one the line uses."""
        self.names = frozenset({p.name for p in meta.players} | {meta.home.name, meta.away.name})

    async def render(self, verdict: Verdict) -> Cue:
        """Approved claim -> broadcast cue, in the chosen language when it can be checked."""
        cue = self._english(verdict)
        if self.lang == "en":
            return cue
        update: dict = {"headline": local_headline(cue.headline, self.lang)}
        if self.translator is not None:
            translated = await self._translate(cue)
            if translated is None:
                update["receipt"] = cue.receipt.model_copy(update={"translation_refused": True})
            else:
                text, model = translated
                update |= {"text": text, "lang": self.lang, "original": cue.text}
                update["receipt"] = cue.receipt.model_copy(update={"translated_by": model})
        return cue.model_copy(update=update)

    async def _translate(self, cue: Cue) -> tuple[str, str] | None:
        """The translation, or None if it states a number the verified line doesn't, twice."""
        reasons: list[str] = []
        for _ in range(2):
            try:
                text, model = await self.translator(cue.alert_id, cue.text, self.lang, reasons)
            except Exception:  # a translator outage costs the language, never the cue
                return None
            invented = invented_numbers(cue.text, text)
            renamed = [n for n in self.names if n in cue.text and n not in text]
            if not invented and not renamed:
                return text, model
            reasons = [f"the translation states {n}, which the line doesn't" for n in invented]
            reasons += [f"keep the name {n} exactly as written, in Latin letters" for n in renamed]
        return None

    def _english(self, verdict: Verdict) -> Cue:
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
            lang="en",
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
        elif alert.kind is AlertKind.GREAT_PASS:
            headline = f"GREAT PASS · {team.short_name}"
            text = f"Great pass from {team.name}: difficulty {m['pass_difficulty']:.0f} of 100."
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
            headline=local_headline(headline, self.lang),
            text=text,
            lang="en",
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
