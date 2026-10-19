# Foundry's judges on the lines that aired

> Written on 2026-10-19 from two runs of `scripts/live foundry-eval --seeds 2`.

Microsoft Foundry's evaluators (azure-ai-evaluation) read every line that aired in unseen matches
(seeds 60-61), each against the fact sheet it was written from, and scored it from 1 to 5 (a pass
is 3 or more). gpt-4.1-mini wrote the lines and the Critic passed them first; gpt-5-mini judged, a
different model, so none graded its own work. Both runs are logged to the Foundry project, where
they show next to the models they judged.

## What the judges found, and what changed

Every line the judges failed for groundedness had passed the Critic, and each was true to its
numbers. What they got wrong was meaning, which code doesn't read:

- an exploratory run (most of its judge calls dropped): "sending the keeper the wrong way", on a
  penalty the facts say only was scored, and "the goalkeeper makes a crucial save for Saltmarsh
  Rovers", for a save the facts don't attribute;
- the measured run below, before the change: "4 interceptions" and "9 ball recoveries", where the
  facts say 4 balls won high (by tackle or interception) and 9 presses. Both numbers are real,
  so the Critic's number check passed them; what each counts was swapped.

The Critic checks numbers and citations by code; a model judge reads for everything else. So the
Narrator's instructions now say: add no detail the facts don't give, not how the keeper moved,
not where the ball went, not whose save or whose chance it was beyond what the facts say. The
second run, on the same matches, narrated afresh:

| Judged for | Before (mean, 1-5) | After |
|---|---|---|
| Groundedness | 4.69 (96.6% passed, 29 judged) | 4.84 (100.0% passed, 25 judged) |
| Relevance | 4.41 (100.0% passed, 27 judged) | 4.65 (100.0% passed, 26 judged) |
| Coherence | 4.42 (100.0% passed, 24 judged) | 4.35 (100.0% passed, 23 judged) |
| Fluency | 3.95 (100.0% passed, 19 judged) | 3.91 (100.0% passed, 22 judged) |

Groundedness, the one the change aimed at, rose to 4.84 with every judged line passing. The others
moved within noise. Two matches a run is a small sample: read it as a direction, not a proof.

After this run, one more line went into the instructions for the swap above: state each number as
what the facts say it counts. It isn't measured yet; the next run will say.

Some judge calls dropped their connection on this machine's network; a call with no verdict
counts neither for nor against, and each row says how many lines were judged.

- Before: https://ai.azure.com/resource/build/evaluation/ece66bdc-7fbd-4948-b46c-dfa3ddd1b087?wsid=/subscriptions/a849f7b9-b97c-4aa2-8e4a-b7603bcce521/resourceGroups/rg-hudhud/providers/Microsoft.CognitiveServices/accounts/hudhud-foundry/projects/hudhud&tid=58c2d73e-ecf6-42b5-8494-5fa13c361ecc
- After: https://ai.azure.com/resource/build/evaluation/435b4b61-6188-4853-a2dd-5588b61f074b?wsid=/subscriptions/a849f7b9-b97c-4aa2-8e4a-b7603bcce521/resourceGroups/rg-hudhud/providers/Microsoft.CognitiveServices/accounts/hudhud-foundry/projects/hudhud&tid=58c2d73e-ecf6-42b5-8494-5fa13c361ecc
