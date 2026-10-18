# ADR 0009: Urdu and Arabic, under the same law

- **Status:** accepted, 2026-10-18; the language itself awaits the owner's review (docs/review/ur-ar.md)
- **Context:** Phase 3. The challenge asks for insights "for fans around the world in multiple
  languages". The owner speaks Urdu and Arabic; HUDHUD speaks both, and English.

## Decision

- **Translate the verified line, never the facts.** The Localizer agent translates the line the
  Critic has already approved, with the Foundry models (the same deployments and ledger as the
  Narrator, so the cue's receipt carries the translation's tokens and cost).
- **The same law in every language.** A translation may state no number the verified line doesn't
  (`critic.invented_numbers`, which reads Eastern Arabic and Persian digits as the numbers they are),
  and it must keep every player and team name exactly as written, in Latin letters, so each can still
  be checked against the match. A translation that breaks either goes back once with the reasons; if
  it still breaks them, the English line airs and the receipt says the translation was refused.
- **Faithful, not embellished.** The first live run added praise the English never said ("a superb
  shot", "fully deserved"); the translator is now told to add nothing.
- **The original stays one tap away.** A translated cue carries its verified English (`Cue.original`).
- **Fixed strings are the owner's call.** The only non-English words HUDHUD writes itself are the
  headline labels; they are drafts until the owner signs them off. Offline (no models), lines stay in
  English under the translated headline, and the studio says so.

## Consequences

- Live, seed 21: Urdu 10 of 10 cues translated, Arabic 9 of 9, no refusals, about $0.005 a match
  each. Urdu renders in Noto Nastaliq Urdu, Arabic in Noto Naskh Arabic, right to left.
- Names in Latin letters inside Urdu and Arabic text read as a technical broadcast would show them;
  transliteration can return once there's a way to check it (a reviewed name table per club).
