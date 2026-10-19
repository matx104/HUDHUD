# Ask the match, measured

> Written by `scripts/live ask-eval` on 2026-10-19. Unseen matches, seeds
> 60, 61; questions asked at 30', 70' and full time.

gpt-4.1-mini answered 57 questions through the Critic, as the studio
does. Each answerable question's truth was counted by code; each unanswerable one has the reason it
can't be answered.

- **Right:** 39 of 39 answerable questions
  (100.0%): verified by the Critic, and stating the true numbers and names.
- **Held back:** 18 of 18 questions the events
  can't answer were declined for the right reason, in fixed words.
- **Caught on the way:** the Critic refused 0 drafts before an answer
  showed (none).
- **Speed and cost:** median 2.9 s an answer, $0.0469 for the run.
- **Failed to reply:** 0 (the model's reply couldn't be read after a retry;
  in the studio the backup model or the offline answerer would have answered).

| Grade | Answers |
|---|---|
| declined, right reason | 18 |
| right | 39 |

"Off the question" is the gap the Critic leaves by design: it proves every number, name and
citation an answer states, not that the answer is the one asked for.

## Before and after

The first run, on the same matches with the same questions, got 39 of 39
answerable questions right but answered 2 of the
18 it should have held back: asked whether a player was injured, the model inferred
"no signs of injury" from his pass counts. Every number in those answers was true, so the Critic
passed them; Foundry's groundedness judge failed both. Three things changed (ADR 0010):

1. Code holds back a question about what event data can't see (a body, a mind, the weather, a
   contract, words spoken) before any model is asked, and the instructions forbid inferring one
   from counts.
2. Which chance was biggest became a fact of its own, so an answer that says so stands on a fact.
3. The judge reads the brief the model was given (the match and the moment), not only the facts.

| Measured | Before | After |
|---|---|---|
| Answered right | 39 of 39 | 39 of 39 |
| Held back, for the right reason | 16 of 18 | 18 of 18 |
| Relevance, Foundry's judge | 4.15 (100.0% passed) | 4.17 (100.0% passed) |
| Groundedness, Foundry's judge | 4.36 (87.9% passed) | 5.0 (100.0% passed) |

Read the after column with two things in mind. Of the 18 held back, the 6 injury
questions were held back by the new code before a model was asked; the model itself declined the
other 12 (what hasn't happened yet, and what isn't about the match). And part of the rise in
groundedness is a fairer judge: the first run marked down answers for saying "in the second half",
which the model had been told and the judge hadn't. Two matches, 57 questions a run, and the judge
answered for 32 to 35 of the 39 verified answers (dropped connections give no verdict, and count
for nothing): read it as a direction, not a verdict.

## Foundry's judges

Each verified answer, judged by gpt-5-mini (a different model from the writer) with
Microsoft Foundry's evaluators: relevance against the question asked, groundedness against the facts
the answer stood on. 1 to 5, pass at 3.

| Judged for | Mean (1-5) | Passed | Answers judged |
|---|---|---|---|
| Relevance | 4.17 | 100.0% | 35 |
| Groundedness | 5.0 | 100.0% | 32 |

## Every answer that wasn't right

None.
