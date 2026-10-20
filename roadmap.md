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
8. **Never a betting tool.** HUDHUD tells what has happened, never what will: no predicted results, scores or next goals, no odds, and no help to anyone placing a bet. Asked about bets or odds, it says so in fixed words, before any model reads the question, and steers away from gambling. Set by the Monarch, 2026-10-20.

## Stage 1 — The court of claims (the hackathon, Oct 17–27, 2026) · IN PROGRESS

Commentary that proves every claim. Five agents (Orchestrator, Scout, Narrator, Critic, Localizer) work over synthetic match events. The Critic rejects anything it can't verify, the broadcast survives agent failure, and cues go out as overlay cues for analysts and casual fans in English, with Urdu and Arabic to follow. Phases and dates are in plan.md.

- **Bridge item, "Ref's call": live since 2026-10-19.** The Scout flags a foul that carries a card or a penalty, the Narrator states the likely decision, and the Critic recomputes it from the cited foul under a lenient, standard or strict profile (court/referee.py). It proves the official's loop on today's agents. The restart has ground truth in the generator; cards wait for Stage 2's generator.
- **HUD²: live since 2026-10-20.** The same match on one central screen, through the referee's, the commentator's or the fan's lens, with overlays, markings and annotations (ADR 0012). Today's first step of the HUD² road below.
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
- **Audit:** every recommendation is kept with its evidence for post-match referee assessment and league review, in a ledger chained by hashes (live since 2026-10-20, ADR 0013), with each match's seal published to a public log so no one can rewrite a decision's record afterwards.
- **Pilot path:** simulation and esports first, then grassroots and academy football, then lower-tier professional trials, and, once each stage has proven itself, the top professional leagues and the biggest international tournaments. Every trial runs inside the competition's protocol and with the approval of the game's law-making body. Bias audits and transparency reports are part of the product, not an afterthought.

## HUD²: the official, seen

Everything above has to reach people's eyes. HUD² is how: one match, each viewer's own lens. Set by the Monarch, 2026-10-20.

- **Today, a screen (built).** One central display with overlays, markings and annotations, through three lenses: the referee's, the commentator's and the fan's. Every action is drawn where it happened, every line is checked by the Critic and pinned to the events it cites, and each viewer switches layers on or off, kept for next time.
- **Next, glasses.** The same lenses on a head-worn display, with the marks anchored to the real pitch instead of a drawing of it. That needs Stage 3's eyes: where the ball and every player are, from the cameras.
- **Then, contact lenses,** as the hardware arrives.
- **Further out, neural interfaces,** only with consent and only once they are proven safe.
- **The end state:** everyone sees the match through a lens shaped to their own needs and preferences: the referee's decision support, the commentator's spotter board, a newcomer's plain-words guide, each in their own language.
- **What never changes:** the evidence law. On any device, a word passed the Critic and a mark is an event that happened. The referee's lens shows the least, never stands between the referee and the players (principle 7), and never decides (principle 2).

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
| HUD²: one screen, three lenses | Each viewer's own lens: glasses, then contact lenses |

## Read along the way

- **BETER, *eFootball performance report* (September 2026)**, [the report](https://mcusercontent.com/1b3a0f97e12c025cc5319cfad/files/f9932d28-0382-d927-d234-b625b699f0d6/BETER_eFootball_Performance_Report1_World_Cup_2026.pdf). A supplier's report to betting operators on esports football during a major international tournament in 2026. What I took from it: big tournaments bring newcomers, and more than half of them stayed, so HUD²'s fan lens explains in plain words; the experience of a match matters as much as the match ("not simply about delivering more matches... making every match a better experience"), the case for HUD²; interest runs before, between and after matches and through the night, which supports the recap and questions after full time, in Urdu and Arabic. Because the report is about betting, it also settled principle 8. Its figures are the supplier's own, with no method behind them: I took ideas from it, not evidence.

## Open questions and risks

- **Rights:** footage and tracking data are owned. Research licences cover research, not deployment.
- **Liability and acceptance:** referees' bodies, competitions and the law-making body decide what an advisory system may do.
- **Bias:** strictness must not drift by team, player or crowd. It has to be measured and published.
- **Latency:** "in a blink" is a hard engineering budget, not a slogan.
