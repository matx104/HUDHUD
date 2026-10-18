# TASK — The Official Ask

> Microsoft × Premier League — **Inside the Game: Developer Hackathon**
> Registration Sep 29 – Oct 20 · Hacking Oct 6 – Oct 27 · Top six notified by Nov 10 · Winners Nov 20 (2026) · Hosted by Microsoft · Innovation Studio platform · $50,000 prize pool
> Source of truth: the **official rules** at github.com/microsoft/insidethegamehackathon (`OFFICIAL RULES.md`, read 2026-10-18; the Monarch's fork is matx104/insidethegamehackathon) and the overview page. The rules prevail over every other statement (rules §11.4).

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

## The official rules: what binds us (read 2026-10-18)

- **Judging period:** Oct 27, 9:00 AM PT – Nov 10, 11:59 PM PT. Two stages:
  - Stage One is pass/fail: does it fit the theme and apply the required technologies?
  - Stage Two scores the five equally weighted criteria below.
- **Prizes per project:** **at most one Grand Prize and one Category Prize** (§4.2, §8). We can't sweep six; we aim for one of each.
- **Testing access (§4.8):**
  - Judges must be able to reach a **working project** (a website, functioning demo or test build), free and without restriction, **until the judging period ends on Nov 10**.
  - A private site needs login credentials in the testing instructions.
  - Judges may also judge on the text, images and video alone.
- **Functionality (§4.3):** the project must install and run consistently, and **work as shown in the video**.
- **Materials in English (§4.9).** Urdu and Arabic output is fine; the pitch, video and test instructions are in English.
- **Original work (§4.6, §4.11):** solely owned. Open source is allowed under its licence; third-party technical help is allowed if the work and ideas are ours.
- **No real footage or data (§4.7):** synthetic, football-realistic data only.
- **Hero technologies, judged under Technological Implementation:**
  - Microsoft Foundry, Agent Framework and **Azure MCP**;
  - **GitHub Copilot Agent Mode**, the GitHub SDK and **GitHub CLI**;
  - Fabric, Azure Apps and AI Services, and Azure databases.
- **Agentic Design** asks explicitly for **"sophisticated agent orchestration, MCP integration, or multi-agent collaboration"**.
- **The challenge's feature list (§4.1 ii, iv):**
  - player identification, with speed and distance tags when thresholds are reached;
  - pass quality: distance, accuracy and a difficulty rating;
  - ball speed and shot speed;
  - auto-eventing from video (optional);
  - control vs chaos, pressure changes and game rhythm;
  - personal modes: favourite club, favourite player, player focus, a single metric.
  - Our generator already emits pass distance, accuracy, difficulty, ball speed and shot speed, but the cues don't surface them yet.

## A secondary summary (pasted 2026-10-18): useful themes, two errors

A third-party summary of the hackathon (it reads as an AI assistant's answer) lists focus areas:
team play styles and tactics, **counterattack and match-flow analysis** (transitions, high-press
efficiency), player performance and spatial AI, and automated recaps and narratives. It also lists
AKS/ACA, Azure SQL, PostgreSQL, Cosmos DB, Azure AI Search vector search, Azure OpenAI, Foundry and
Semantic Kernel. **Two claims in it are wrong for this hackathon and must not steer us:**
- "official football data" and "30+ seasons of historical data": the rules require synthetic data
  (§4.7);
- Semantic Kernel: its successor, Microsoft Agent Framework, is the named hero technology.

The themes match Reactor 27536's (docs/reference/reactor-27536.md). The counterattack and press
ideas are in plan.md.

## Key dates (official overview page, pasted 2026-10-18)

| When (Pacific) | When (Karachi, PKT) | What |
|---|---|---|
| Sep 29 | | registration opens |
| Oct 6 | | hacking period starts, submissions open |
| **Oct 20, 12:00 PM** | **Oct 21, 00:00** | **registration deadline** (invitation to Innovation Studio follows) |
| **Oct 27, 11:59 PM** | **Oct 28, 11:59 AM** | **submissions close.** We submit on the evening of Oct 27 PKT, with a buffer |
| Oct 27, 9:00 AM – Nov 10, 11:59 PM | | **judging period: the live demo must stay up and free to use** |
| by Nov 10 | | **top six projects selected and notified** |
| Nov 20 | | winners announced |

The showcase site counts down to the close (`deadline` in `site/config.js`).

## The overview page, in its own words (pasted 2026-10-18)

> Build AI-powered solutions that transform synthetic, football-realistic data into explainable match intelligence, real-time narratives, and automated match recaps for studio, broadcast, or streaming scenarios. Compete for a share of **$50,000 USD** in cash prizes, event tickets, and more.

**What the strongest submissions will leverage:**
- GitHub and **GitHub Copilot**
- **Microsoft Foundry** and Azure AI Services
- **Microsoft Fabric** and other Azure database and analytics services
- Azure cloud-native services

They should create AI-powered applications and agents that:
1. analyze match events in real time;
2. generate stories, highlights and recaps;
3. explain key moments and tactical patterns;
4. expand datasets for AI and analytics;
5. deliver insights for fans around the world in multiple languages;
6. deliver personalized experiences for studios, streaming platforms and fans.

**Where we stand against that list (2026-10-18):**
- **Covered or planned:** 1 (the Scout, live), 3 (the Critic-checked claims, the momentum ADR), 4 (the seeded generator with hidden ground truth *is* dataset expansion), 5 (EN now, UR/AR in Phase 3), 6 (analyst and casual modes), Foundry (Phase A), cloud-native (Phase 3).
- **Decided by the Monarch (2026-10-18):**
  - **Registered** for the hackathon (the deadline was Oct 20, 12:00 PM PT).
  - **GitHub Copilot agent mode** is in the build: the Monarch uses it (GitHub Student plan). The repo carries `.github/copilot-instructions.md` so it follows the evidence law, and `.vscode/mcp.json` gives it the Azure MCP Server, signed in as the project's CLI.
  - **The audit trail** is on Azure Cosmos DB's free tier, and **Microsoft Fabric** mirrors it into OneLake for analytics during the 60-day trial (ADR 0004).
  - Recaps (2) are planned for Phase 3.

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
