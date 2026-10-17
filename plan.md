# PLAN — Build Plan (Oct 18 → Oct 27)

> The calendar is law. Every phase has a definition of done; when a phase overruns, cut from the bottom of its scope list — never borrow from the next phase's first item (video + submission are untouchable).

## Phase 0 — Weekend intel (Oct 17–19, Monarch's Playwright session)

- [x] **WATCHED (2026-10-18, via transcript; notes in docs/reference/reactor-27536.md): Reactor session "Build AI-powered soccer insights apps with AKS and ACA"** — <https://developer.microsoft.com/en-us/reactor/events/27536/> — aired Oct 14 (recording embedded on page), Brian Benz, part of the hackathon's own series. Reference architecture for deploying AI apps **and agents on AKS + ACA** with PL-inspired scenarios (play styles, counterattacks, performance patterns) — *"practical guidance attendees can extend into their hackathon projects."* This is Microsoft showing the Cloud-Native lane's expected shape — watch before architecture lock. Also check the **Series Page** link there for sibling episodes
- [ ] Detail pass on the 18 HIGH-tier projects (inspiration.md list) — what they promise vs. what they show; update threat tiers — **DEFERRED 2026-10-17:** automated browsing stopped at the gallery sign-in. Monarch reviews the 18 by hand via the local-only review page `site/review/` (gitignored, never deployed; "Copy notes as Markdown" brings the notes back)
- [ ] Sharpen the differentiation sentence (inspiration.md §Differentiation memo) against what the top 10 actually build — gated on the detail pass
- [ ] Check platform Resources tab for a sample dataset / schema (if one exists, it replaces the generator in Phase 1) — **DEFERRED** to the Monarch's manual pass; generator built meanwhile, so a platform schema would become an adapter, not a rewrite
- [x] Pick name — **HUDHUD** (Monarch, 2026-10-17; story in brand.md, set in `site/config.js` + `court/config.py`)
- [ ] Buy domain (re-run RDAP day-of; Cloudflare/Porkbun) — candidates in project-names.md §H, lead: hudhud.football
- **Done when:** differentiation memo v2 written, name+domain owned.

## Phase 1 — Architecture lock + skeleton (Oct 18–20)

- [ ] Activate Azure for Students ($100 credit — the ceiling, not the budget) — Monarch-manual
- [x] **Synthetic match event generator** — `packages/event-schema` (2026-10-17). Deterministic per seed; calibrated over 100 seeds to ~3.0 goals, 78.5% pass completion, 29 shots, ~320 pressures, 46 tackles per match. Emits hidden ground-truth *momentum spells* (never streamed) so Scout detection can be scored. JSON Schema committed for the web side
- [~] Agent spine — Orchestrator + Scout + Narrator + Critic + Localizer on Agent Framework 1.22 workflow (see docs/adr/0001). Shared `MatchState`, typed handoff contracts. **Offline backends only:** template Narrator, EN-only Localizer; Foundry-hosted LLM backends wait on Azure activation
- [x] Repo scaffold: `apps/api` (package `court`), `packages/event-schema` (package `match_events`); CI from first commit. `apps/web` deferred to Phase 2 (nothing to render until the cue stream is real)
- **Done when:** one synthetic match flows end-to-end Scout→Narrator→Critic→console, with tests green. — **MET 2026-10-17** (offline backends): `make demo`, 48 tests green

## Phase 2 — Core build (Oct 21–23)

- [ ] Scout: live pattern detection — momentum swings, chance quality (xG-style), pressure shifts, control-vs-chaos index; severity-ranked live alert feed
  - [x] **Momentum, measured (2026-10-18, ADR 0002):** baseline-relative completion + final-third rate, held 3 min; scored against hidden ground truth by `make eval`. Sure-call operating point (Monarch): precision 62% / recall 26% on unseen seeds, vs 36% / 69% before. Momentum demo match: **seed 21**
  - **Eval finding (2026-10-17, seed 7):** only 1 of 5 momentum alerts overlaps a true spell. All three true spells were the away side's, yet 4 of the 5 alerts went to the stronger home side. The Scout reads *relative* dominance, so it reports a stronger team's baseline as momentum. Fix: baseline-relative (anomaly) detection, i.e. each side vs its own match-to-date rate (the SOCIRIS pattern). Score precision/recall against `GroundTruth.spells` over N seeds
- [ ] Critic momentum evidence rule — `court/critic.py::momentum_rule` is a TODO(human); momentum claims fail closed (NO_RULE → spiked) until it's registered; `tests/test_momentum_rule.py` (3 tests, skipped until then) defines what it must do
- [ ] Narrator: live tactical narrative + key-moment explainers (the "why", cited to events)
- [x] **Azure Phase A (2026-10-18):** Foundry resource `hudhud-foundry` and project `hudhud` in UAE North, `gpt-5-mini` (primary) and `gpt-4.1-mini` (backup) deployed, Entra-only (docs/azure.md)
- [ ] **Foundry Narrator:** behind the `Narrator` protocol via `agent-framework-foundry` (`FoundryChatClient`), structured JSON claims the Critic checks; the template narrator stays the default for tests and CI; a token-cost meter from the first call
- [ ] **The rules' feature list (§4.1 ii):** pass-quality cues (distance, accuracy, difficulty), speed cues (ball and shot speed), player tags. The generator already emits every field
- [ ] **Personal modes (§4.1 i e):** favourite club, favourite player, player-focus, single-metric
- [ ] **Receipts on every cue** (Reactor 27536): verified or detection-only, numbers checked, model, latency, tokens, estimated cost, evidence IDs
- [ ] **Narrator eval, "evaluation decides which model serves"** (Reactor 27536): `gpt-5-mini` vs `gpt-4.1-mini` on the same alerts; first-attempt Critic pass rate, grounding failures, latency, cost
- [ ] **"What this data can't tell you"** on the site and in the UI: momentum precision, synthetic clubs and players, no video
- [ ] **Counterattack and high-press alerts** (overview themes): transitions after a won tackle or interception, press efficiency from pressure events
  - Copy bug seen in the seed-7 run: the momentum template pluralizes blindly ("1 box entries", "1 shots")
- [ ] **Critic: the moat — adversarial verification.** Every claim must cite event evidence; rejections visible in UI with reasons; rewrite loop
- [ ] Overlay cue stream: timed, machine-readable JSON (broadcast-renderer ready) — the platform's rendering-partner lane
- [ ] Personalization: analyst mode vs casual fan mode; club/player focus; preference drives both content AND depth
- **Done when:** live demo runs one match end-to-end in the UI with visible evidence links + at least one on-screen Critic rejection.

## Phase 3 — Differentiators + polish (Oct 24–25)

- [ ] **Failure recovery demo (0/150 competitors claim it):** kill an agent mid-match on camera → orchestrator detects, retries/reassigns, broadcast never drops; surfaced as a feature, not a footnote
- [ ] Multilingual: EN native + UR + AR native-register output (owner-review loop on non-English strings — flag, don't self-trust)
- [ ] Automated recap: post-match report, evidence-linked, exportable
- [ ] Observability: agent traces, token/cost meter vs the $100 ceiling (the day-job flex)
  - Application Insights + Log Analytics + Foundry tracing; a HUDHUD workbook with the charts; a **local-only control room** page in the site whose buttons open the Azure portal views (cost, budget, app health, AI usage, AI logs) for the demo recording. Public site never shows it: the links carry subscription and tenant IDs
- [ ] **MCP server:** expose the Critic (`verify_claim`) and match state as MCP tools, so any assistant (Copilot included) can have a football claim checked. Agentic Design scores "MCP integration"; Azure MCP is a named hero technology
- [ ] **Judge-accessible live demo (rules §4.8):** free, unrestricted, up through **Nov 10** (judging end); Container Apps. Credit expires Nov 13, so it lasts
- [ ] **"Ref's call" cue** (roadmap.md bridge item, **cut first**, only if Phase 2 lands by Oct 23): Scout flags a foul tackle → Narrator states the likely decision → Critic checks it against the evidence under a lenient/standard/strict profile
- **Done when:** recovery demo + trilingual output + recap all work in one run.

## Phase 4 — Ship kit (Oct 26)

- [ ] README: pitch (what/stack/problem), architecture diagram, quickstart, evidence philosophy
- [ ] **Video: 110 seconds, hard law** — 15s problem → 45s live demo → 30s Critic rejection (money shot) → 20s architecture + multilingual. No third-party trademarks/logos, no unlicensed music. Public URL (YouTube unlisted is fine — link must be public)
- [ ] Repo goes **public**; showcase site if time allows (domain from Phase 0) — **scaffold started 2026-10-17:** `site/` with an evidence-chain hero from a real seed-7 run (CI drift-checked). **Live 2026-10-17** at matx104.github.io/HUDHUD: Pages source = GitHub Actions, `pages.yml` deploys only `site/` on every push touching it (repo stays private until submission). **2026-10-18:** rebuilt as a hash-routed SPA (problem, goal, how, recovery, data, why, roadmap, name, who) with SEO tags, OG card, icons. At submission: flip `repoPublic` in `site/config.js` (shows the Code links); on domain purchase: change `siteUrl` + the `<head>` copies (tests/site fails until they agree)
- **Done when:** submission package complete per task.md checklist.

## Phase 5 — Submit (Oct 27)

- [ ] Submit on Innovation Studio by **evening PKT** (deadline = Oct 28 ~11:59 AM PKT; never deadline-day heroics)
- [ ] Pitch text: what was built, Microsoft/Azure stack used, problem solved — one paragraph, no fluff
- **Done when:** confirmation screenshot in #pl-hackathon.

## Open decisions (from the official rules, 2026-10-18)

- **GitHub Copilot Agent Mode** is a named hero technology and a multi-agent option ("GitHub Copilot, Microsoft Agent Framework, A2A"). How does it enter the build story?
- **Microsoft Fabric** is named; we planned Cosmos DB for the audit trail.

## Scope law (cut order, first to go)

0. "Ref's call" cue (roadmap bridge) → 1. Showcase site (repo README carries launch) → 2. Extra languages beyond UR/AR → 3. What-if simulation → 4. Recap export formats (one format ships) → 5. NEVER cut: Critic loop, recovery demo, video, submission buffer.

## Standing risks

- **MatchMind (126341)** claims our EN/UR/AR trio on Agent Framework — depth + recovery beat them; watch after weekend detail pass
- Azure $100 ceiling — Foundry token burn is the risk; cap demo match length, cache aggressively, meter from day one
- Dataset unknown until Resources tab check — generator path is the default plan (pillar v of the brief explicitly invites synthetic dataset creation)
