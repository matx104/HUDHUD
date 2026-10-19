# ROADMAP — Onwards & Upwards

> HUDHUD does not stop at the hackathon. The hackathon build is stage one of a longer road whose end is an **AI fourth official**: an evidence-first assistant that sits beside the referee team. Agreed by the Monarch, 2026-10-17. Each stage has an exit gate; a stage starts only when the one before it has passed its gate.

## The north star: the fourth official

An official that watches every moment of the match and judges calls in a blink, at the strictness the competition has chosen. It shows the evidence for every decision and explains it to the referee, the broadcast and the crowd, each in their own language and at their own depth.

**The ambition: a standard part of the game.** In the world's most prestigious international tournaments, at every level beneath them and above them, as much a part of football as the assistant referees, without taking anything away from the game's beauty: the flow, the drama and the referee stay; what HUDHUD adds is understanding. Set by the Monarch, 2026-10-19.

**It advises, and the human referee decides.** This follows where the game is already going. Semi-automated offside builds the offside line with AI, and a human still signs it off. Research such as X-VARS (CVPR 2024 workshop) shows a model can classify fouls from video and explain them against the Laws, but no deployed system judges subjective calls. That gap is the destination.

## Principles that hold at every stage

1. **Evidence before verdict.** Every call cites what it saw. No evidence, no call: the system fails closed, exactly as the Critic does today.
2. **The human decides.** HUDHUD recommends and explains. It never overrules the referee.
3. **Strictness is a setting, not a mood.** A competition picks a calibrated profile, and the same incident gets the same call every time.
4. **The Laws come first.** The Laws of the Game are encoded as checkable rules, and any judgment the rules can't settle is flagged as judgment.
5. **Explain to everyone.** The referee gets the reasoning, the broadcast gets the evidence, and the crowd gets the call in its own language.
6. **Never go dark.** When something fails, the system degrades, announces it and recovers, as the Orchestrator does today.
7. **Add, never take away.** The game keeps its flow, its drama and its people. Nothing HUDHUD does may slow a restart, mute a celebration or stand between the referee and the players; it earns its place only by adding understanding.

## Stage 1 — The court of claims (the hackathon, Oct 17–27, 2026) · IN PROGRESS

Commentary that proves every claim. Five agents (Orchestrator, Scout, Narrator, Critic, Localizer) work over synthetic match events. The Critic rejects anything it can't verify, the broadcast survives agent failure, and cues go out as overlay cues for analysts and casual fans in English, with Urdu and Arabic to follow. Phases and dates are in plan.md.

- **Bridge item, "Ref's call": live since 2026-10-19.** The Scout flags a foul that carries a card or a penalty, the Narrator states the likely decision, and the Critic recomputes it from the cited foul under a lenient, standard or strict profile (court/referee.py). It proves the official's loop on today's agents. The restart has ground truth in the generator; cards wait for Stage 2's generator.
- **Exit gate:** entry submitted, repo public, the 110-second video live on YouTube (the owner's channel, MATX104: @monarch-_-mat).

## Stage 2 — The decision explainer (after submission, Nov 2026 → Q1 2027)

When the referee makes a call, HUDHUD explains it.

- **Inputs:** referee decisions arrive as events (foul, card, offside, penalty, VAR review), alongside the play that led to them.
- **Generator:** extend the generator to emit fouls with severity, cards, free kicks, offside positions and VAR reviews, with hidden ground-truth decisions, as it already hides ground-truth momentum.
- **Agents:** the Narrator drafts the explanation and the Critic checks it against the evidence and the encoded Law. The Localizer renders it for the stadium screen, the broadcast and the app, in English, Urdu and Arabic.
- **Strictness profiles:** lenient, standard and strict, calibrated against the generator's ground truth.
- **Evaluation:** agreement with ground-truth decisions over many seeds. The target is set after the first baseline, never before it. Explanations are reviewed by a panel of qualified referees.
- **Exit gate:** the baseline is measured and published, and the referee panel signs off the explanations of one complete match.

## Stage 3 — Perception: the Scout gets eyes (2027)

From event logs to seeing the incident.

- **Data:** open research datasets first, such as SoccerNet's multi-view foul data, under their licence terms. Then player tracking and pose. No broadcast footage without rights.
- **Models:** foul type and severity classified from multiple camera angles, benchmarked against published results. The cited evidence becomes clip and frame references, so the evidence chain survives the jump from events to video.
- **Exit gate:** the system matches published baselines on a public benchmark, and every prediction carries its cited frames.

## Stage 4 — The fourth official (the north star)

Real-time advice to the referee team.

- **Speed:** a recommendation with its evidence faster than a VAR check takes today.
- **Prediction:** flashpoint risk (a challenge likely to escalate, a game heading out of control), so officials can act before the incident instead of reviewing it afterwards.
- **The strictness spectrum:** per competition, published in advance and applied consistently.
- **Talking to the crowd:** scripted announcements for the stadium screen and PA, and explanations in the app, in the fan's language.
- **Audit:** every recommendation is kept with its evidence for post-match referee assessment and league review.
- **Pilot path:** simulation and esports first, then grassroots and academy football, then lower-tier professional trials, and, once each stage has proven itself, the top professional leagues and the biggest international tournaments. Every trial runs inside the competition's protocol and with the approval of the game's law-making body. Bias audits and transparency reports are part of the product, not an afterthought.

## Beyond

- **Referee development:** match replays with the official's reasoning, for training and assessment.
- **Consistency analytics:** how strictly each competition is really refereed, measured from the evidence.
- **Other sports:** the same court for any game with laws and evidence.

## What carries forward from today's code

| Today (stage 1) | At the north star |
|---|---|
| Scout: detects patterns in events | Perception: sees the incident |
| Narrator: drafts the claim | Drafts the recommended decision |
| Critic: verifies against the events | Checks the decision against the evidence and the Laws |
| Localizer: casual or analyst, by language | Speaks to the referee, the broadcast and the crowd |
| Orchestrator: retries, degrades, recovers | Meets the latency budget and never goes silent |
| Evidence chain | Decision audit trail |

## Open questions and risks

- **Rights:** footage and tracking data are owned. Research licences cover research, not deployment.
- **Liability and acceptance:** referees' bodies, competitions and the law-making body decide what an advisory system may do.
- **Bias:** strictness must not drift by team, player or crowd. It has to be measured and published.
- **Latency:** "in a blink" is a hard engineering budget, not a slogan.
