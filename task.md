# TASK — The Official Ask

> Microsoft × Premier League — **Inside the Game: Developer Hackathon**
> Sep 29 – Nov 21, 2026 · Hosted by Microsoft · Innovation Studio platform
> Source of truth: the official pages (overview pasted 2026-10-15; Challenge-menu brief still unread — fetch when logged in).

## The ask, verbatim

> "Build an AI-powered solution that transforms synthetic, football-realistic data into **explainable match intelligence, real-time narratives, automated recaps, and personalized experiences** for fans, studios, broadcasters, and streaming platforms."
>
> "…build an AI-driven **application or agent** that turns synthetic football events into **useful, understandable, and engaging** match intelligence."

**Hard data constraint:** projects must use **synthetic, football-realistic data**. No real Premier League match data is redistributed to participants. Dataset format/schema unknown until the Challenge-menu brief is read — **this is the #1 open unknown.**

## Decoded — four output classes + four audiences

- **Explainable match intelligence** — not "AI says X dominated" but *why*, with event evidence
- **Real-time narratives** — live during the match, not only post-hoc
- **Automated recaps** — the 90-minute story writes itself
- **Personalized experiences** — for fans, studios, broadcasters, streaming platforms

## Judging rubric — 20% × 5 pillars

1. **Technological Implementation** — quality practices, effective use of hero technologies, well-structured/maintainable code
2. **Agentic Design & Innovation** — creative agentic AI patterns, sophisticated orchestration/multi-agent collaboration, novel implementations
3. **Real-World Impact & Applicability** — significance of problem, production readiness, impact on developers/businesses/users
4. **User Experience & Presentation** — intuitive UX, clear value communication in demo, balanced frontend/backend
5. **Adherence to Hackathon Category** — comply with the chosen category description

## Prize categories (6)

- 🏆 **Grand Prize: First Place** — ~$4K cash + PL digital ticket (~$1K) + $50 voucher per member + social feature
- 🏆 **Grand Prize: Second Place** — ~$2.5K cash + ticket + voucher per member
- 🧠 **Best Use of Microsoft Foundry** — ~$1.5K per member
- 💼 **Best Enterprise Solution** — ~$1.5K per member
- 💡 **Best Multi-Agent Orchestration** — ~$1.5K per member — *judges score: distinct agent roles, shared state, effective handoffs, failure recovery, end-to-end outcome a single agent couldn't achieve*
- 🎨 **Best Azure Cloud-Native Integration** — ~$1.5K per member

## Submission requirements (hard)

- New project (new repo, new code — patterns reusable, old repos are not)
- Project pitch/description: what was built, Microsoft/Azure stack used, problem solved
- **Demo video < 2:00 HARD** — judges NOT required to watch past two minutes; public URL (YouTube/Vimeo/Facebook/Youku); shows the project functioning; **no third-party trademarks, no copyrighted/unlicensed music**
- **GitHub repo must be PUBLIC** — entry not considered otherwise

## Key dates

- Oct 6 — submissions open
- **Oct 27, 11:59 PM PT — submissions close** (= Oct 28 ~11:59 AM PKT; submit by evening PKT with buffer)
- **Nov 20 — winners announced**

## Constraints we've set ourselves

- **Solo build** (Monarch's decision — prize math + full ownership)
- **Azure spend discipline** — don't break the bank on a non-guaranteed win; free-tier/credits first, cheapest credible footprint; Azure credit status needs review before architecture locks
- **Calendar:** Oct 17 IBA SANS case first → Oct 18–20 explore/architect → Oct 21–25 build → Oct 26 polish + 110-second video → Oct 27 submit
- **Video law (110s):** 15s problem → 45s live demo → 30s Critic rejecting an unevidenced claim (money shot) → 20s architecture + multilingual

## THE CHALLENGE BRIEF — full text (received 2026-10-16, Monarch paste)

> **Challenge name: "The Synthetic Match Insights Engine for Premier League Studio"** — *"An AI insights engine runs on Azure that explains the game beyond the stats, turning football events into real-time insights, key narratives and recaps — personalized for every fan, for studio and streaming use."* (198 projects linked at time of read)

**The one-pipeline-five-stages law (the brief's spine):**
1. **Ingest** synthetic match events as they happen (passes, shots, tackles, possession changes, pressure events, match metadata)
2. **Interpret** into meaningful football statistics, patterns, and context
3. **Explain** why a moment matters — not only that it happened (control vs. chaos, tactical pressure changes, game rhythm)
4. **Render** insight that can sit on screen alongside the match — timed, machine-readable enough for synchronized graphical overlays on a live feed (the platform's rendering partner path)
5. **Personalize** — the same intelligence reaches a data-hungry analyst and a casual fan as two genuinely different experiences: custom modes, favorite clubs/players, player-focus mode, "and welcome many more ideas"

**The both-and law (verbatim logic):** *"a Project that only generates metrics has no audience, and a solution that only personalizes has nothing to personalize."* Overlays-lane OR audience-lane OR both — both wins.

**Real-time features named by the brief (ii):**
- Player identification — real-time name tagging, optional speed/distance indicators on threshold triggers
- Pass quality — distance, accuracy, difficulty rating
- Speed metrics — ball speed, shot speed
- Auto-eventing — model over incoming video feed generating the above automatically (not hand-tagged)

**The other pillars:** (iii) narrative generation — key narratives, player-performance context, milestones, recaps · (iv) explainability — *why* moments matter: control vs chaos, tactical pressure, game rhythm · (v) data innovation — create/extend synthetic datasets · (vi) multi-language storytelling for global studio/streaming.

**Accepted forms:** AI agent, workflow, integration, data platform, analytics experience, automation, or new experience — responsive enough for live play.

## Constraints update (2026-10-16)

- **Azure budget:** no existing benefits. **Azure for Students** available (edu email + GitHub Student Pack) — $100 credit, no credit card. Architecture assumes ~$100 total spend ceiling; "spend depends on the project" — design to the free/student tier first, justify every paid service by name.

## Competition intel (first pass, from gallery card names)

Crowded lanes: match-intelligence dashboards (MatchMind ×2, MatchPulse, MatchLens, TactIQ/TactiCore, Touchline AI), multilingual commentary (Sauti, Msimulizi — Swahili lane taken), accessibility (Audio Eyes), what-if (Second Guess). **The example card project "Synthetic Match Insights Engine" IS our fusion shape — multi-agent pipeline + studio UI + multilingual + overlays + personalized.** Validation + warning in one: the shape is right, and it is no longer differentiating by itself. Differentiators to press: evidence-chain explainability (Critic/isnad — adversarial verification, few will build it), enterprise/production-readiness discipline, broadcast-overlay machine-readability. Full study: inspiration.md once the gallery extraction lands.

## Open unknowns

- [x] ~~Challenge-menu brief~~ — **RECEIVED 2026-10-16** (above). Note: brief describes event types but no formal dataset schema/format — synthetic data may be ours to generate (pillar v invites it); confirm whether a sample dataset ships on the platform (resources tab) at next login
- [x] ~~Azure credits~~ — student plan path chosen ($100 credit, no card); activate when architecture locks
- [ ] **Gallery extraction → inspiration.md** — Claude Code lane: persistent Playwright session (login once, save storageState) → harvest all 198 via selectors+snippet in inspiration.md → inspiration-projects.json + register update. WAZIR walled (login.microsoftonline.com OAuth, verified)
- [ ] Final name + domain purchase (see project-names.md — depends on chosen solution shape)
