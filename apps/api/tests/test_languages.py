"""Urdu and Arabic: the verified line, translated under the same number law (ADR 0009)."""

from court.contracts import AlertKind, Claim, Cue, Side, Verdict
from court.localizer import AWAITING_REVIEW, LABELS, Localizer, local_headline
from court.narrator import TemplateNarrator
from court.orchestrator import run_match


def _verdict(text="Kai Morsen scores from 8 m, xG 0.33.", headline="GOAL · SAL 0-1 BRK"):
    claim = Claim(
        id="a1.1",
        alert_id="a1",
        attempt=1,
        kind=AlertKind.GOAL,
        team=Side.AWAY,
        period=1,
        t=330.0,
        as_of_seq=119,
        severity=1.0,
        headline=headline,
        text=text,
        citations=("e00118", "e00119"),
    )
    return Verdict(claim=claim, reasons=(), numbers_checked=2)


def _translator(*answers):
    calls = []

    async def translate(alert_id, line, lang, reasons):
        calls.append(reasons)
        return answers[len(calls) - 1], "gpt-4.1-mini"

    return translate, calls


async def test_a_faithful_translation_airs_with_its_translator_on_the_receipt():
    translate, _ = _translator("کائی مورسن نے 8 میٹر سے گول کیا، xG 0.33۔")
    cue = await Localizer(lang="ur", mode="analyst", translator=translate).render(_verdict())
    assert cue.lang == "ur" and cue.text.startswith("کائی")
    assert cue.headline == "گول · SAL 0-1 BRK"
    assert cue.receipt.translated_by == "gpt-4.1-mini" and not cue.receipt.translation_refused
    assert cue.original == "Kai Morsen scores from 8 m, xG 0.33."


async def test_eastern_arabic_digits_are_the_same_numbers():
    translate, _ = _translator("سجل كاي مورسن من ٨ أمتار، xG ٠٫٣٣.")
    cue = await Localizer(lang="ar", mode="analyst", translator=translate).render(_verdict())
    assert cue.lang == "ar" and cue.headline.startswith("هدف")


async def test_an_invented_number_goes_back_once_then_english_airs():
    translate, calls = _translator("گول 30 میٹر سے!", "گول 25 میٹر سے!")
    cue = await Localizer(lang="ur", mode="analyst", translator=translate).render(_verdict())
    assert calls[1] == ["the translation states 30, which the line doesn't"]
    assert cue.lang == "en" and cue.text == "Kai Morsen scores from 8 m, xG 0.33."
    assert cue.receipt.translation_refused and cue.headline.startswith("گول")


async def test_the_retry_can_fix_it():
    translate, _ = _translator("گول 30 میٹر سے!", "کائی مورسن نے 8 میٹر سے گول کیا۔")
    cue = await Localizer(lang="ur", mode="analyst", translator=translate).render(_verdict())
    assert cue.lang == "ur" and "8" in cue.text


async def test_a_translator_outage_costs_the_language_not_the_cue():
    async def down(*_):
        raise ConnectionError("no model answers")

    cue = await Localizer(lang="ar", mode="analyst", translator=down).render(_verdict())
    assert cue.lang == "en" and cue.receipt.translation_refused


def test_headlines_keep_codes_and_scores():
    assert local_headline("MOMENTUM · SAL on top", "ur") == "میچ پر گرفت · SAL حاوی"
    assert local_headline("GREAT PASS · HAR", "ar") == "تمريرة رائعة · HAR"
    assert local_headline("BIG CHANCE · SAL", "en") == "BIG CHANCE · SAL"


async def test_without_a_model_the_lines_stay_english_under_local_headlines(swing_match):
    outputs = []
    await run_match(
        list(swing_match.stream()),
        sink=outputs.append,
        narrator=TemplateNarrator(),
        localizer=Localizer(lang="ar"),
    )
    cues = [o for o in outputs if isinstance(o, Cue)]
    assert cues and all(c.lang == "en" for c in cues)
    # Every headline in the owner's signed-off words (docs/review/ur-ar.md); a new kind waits in
    # English, and only while it awaits that review.
    assert all(
        c.headline.split(" · ")[0] in set(LABELS["ar"].values()) | set(AWAITING_REVIEW)
        for c in cues
    )
    assert {"هجمة مرتدة", "ضغط عالٍ", "قرار الحكم"} <= {c.headline.split(" · ")[0] for c in cues}
    for lang in ("ar", "ur"):
        assert not set(AWAITING_REVIEW) & set(LABELS[lang])
        assert set(LABELS[lang]) == set(LABELS["ar"])


async def test_a_name_must_survive_translation_as_written():
    translate, calls = _translator(
        "سجل كاي مورسن من 8 أمتار، xG 0.33.", "سجل Kai Morsen من 8 أمتار، xG 0.33."
    )
    localizer = Localizer(lang="ar", mode="analyst", translator=translate)
    localizer.names = frozenset({"Kai Morsen", "Brackenfield"})
    cue = await localizer.render(_verdict())
    assert calls[1] == ["keep the name Kai Morsen exactly as written, in Latin letters"]
    assert cue.lang == "ar" and "Kai Morsen" in cue.text
