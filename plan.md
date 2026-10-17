# PLAN — Build Plan (Oct 18 → Oct 27)

> The calendar is law. Every phase has a definition of done; when a phase overruns, cut from the bottom of its scope list — never borrow from the next phase's first item (video + submission are untouchable).

## Phase 0 — Weekend intel (Oct 17–19, Monarch's Playwright session)

- [ ] **WATCH: Reactor session "Build AI-powered soccer insights apps with AKS and ACA"** — <https://developer.microsoft.com/en-us/reactor/events/27536/> — aired Oct 14 (recording embedded on page), Brian Benz, part of the hackathon's own series. Reference architecture for deploying AI apps **and agents on AKS + ACA** with PL-inspired scenarios (play styles, counterattacks, performance patterns) — *"practical guidance attendees can extend into their hackathon projects."* This is Microsoft showing the Cloud-Native lane's expected shape — watch before architecture lock. Also check the **Series Page** link there for sibling episodes
- [ ] Detail pass on the 18 HIGH-tier projects (inspiration.md list) — what they promise vs. what they show; update threat tiers — **BLOCKED 2026-10-17:** Playwright MCP needs Chrome (`/opt/google/chrome` missing) + Monarch's Microsoft login
- [ ] Sharpen the differentiation sentence (inspiration.md §Differentiation memo) against what the top 10 actually build — gated on the detail pass
- [ ] Check platform Resources tab for a sample dataset / schema (if one exists, it replaces the generator in Phase 1) — **BLOCKED** (same login); generator built meanwhile, so a platform schema would become an adapter, not a rewrite
- [ ] Pick name from project-names.md + buy domain (re-run RDAP day-of; Cloudflare/Porkbun; cheap TLDs only) — RDAP re-verified 2026-10-17, shortlist unchanged; **awaiting Monarch's pick**
- **Done when:** differentiation memo v2 written, name+domain owned.

## Phase 1 — Architecture lock + skeleton (Oct 18–20)

- [ ] Activate Azure for Students ($100 credit — the ceiling, not the budget) — Monarch-manual
- [x] **Synthetic match event generator** — `packages/event-schema` (2026-10-17). Deterministic per seed; calibrated over 100 seeds to ~3.0 goals, 78.5% pass completion, 29 shots, ~320 pressures, 46 tackles per match. Emits hidden ground-truth *momentum spells* (never streamed) so Scout detection can be scored. JSON Schema committed for the web side
- [~] Agent spine — Orchestrator + Scout + Narrator + Critic + Localizer on Agent Framework 1.22 workflow (see docs/adr/0001). Shared `MatchState`, typed handoff contracts. **Offline backends only:** template Narrator, EN-only Localizer; Foundry-hosted LLM backends wait on Azure activation
- [x] Repo scaffold: `apps/api` (package `court`), `packages/event-schema` (package `match_events`); CI from first commit. `apps/web` deferred to Phase 2 (nothing to render until the cue stream is real)
- **Done when:** one synthetic match flows end-to-end Scout→Narrator→Critic→console, with tests green. — **MET 2026-10-17** (offline backends): `make demo`, 48 tests green

## Phase 2 — Core build (Oct 21–23)

- [ ] Scout: live pattern detection — momentum swings, chance quality (xG-style), pressure shifts, control-vs-chaos index; severity-ranked live alert feed
  - **Eval finding (2026-10-17, seed 7):** only 1 of 5 momentum alerts overlaps a true spell. All three true spells were the away side's, yet 4 of the 5 alerts went to the stronger home side. The Scout reads *relative* dominance, so it reports a stronger team's baseline as momentum. Fix: baseline-relative (anomaly) detection, i.e. each side vs its own match-to-date rate (the SOCIRIS pattern). Score precision/recall against `GroundTruth.spells` over N seeds
- [ ] Critic momentum evidence rule — `court/critic.py::momentum_rule` is a TODO(human); momentum claims fail closed (NO_RULE → spiked) until it's registered
- [ ] Narrator: live tactical narrative + key-moment explainers (the "why", cited to events)
- [ ] **Critic: the moat — adversarial verification.** Every claim must cite event evidence; rejections visible in UI with reasons; rewrite loop
- [ ] Overlay cue stream: timed, machine-readable JSON (broadcast-renderer ready) — the platform's rendering-partner lane
- [ ] Personalization: analyst mode vs casual fan mode; club/player focus; preference drives both content AND depth
- **Done when:** live demo runs one match end-to-end in the UI with visible evidence links + at least one on-screen Critic rejection.

## Phase 3 — Differentiators + polish (Oct 24–25)

- [ ] **Failure recovery demo (0/150 competitors claim it):** kill an agent mid-match on camera → orchestrator detects, retries/reassigns, broadcast never drops; surfaced as a feature, not a footnote
- [ ] Multilingual: EN native + UR + AR native-register output (owner-review loop on non-English strings — flag, don't self-trust)
- [ ] Automated recap: post-match report, evidence-linked, exportable
- [ ] Observability: agent traces, token/cost meter vs the $100 ceiling (the day-job flex)
- **Done when:** recovery demo + trilingual output + recap all work in one run.

## Phase 4 — Ship kit (Oct 26)

- [ ] README: pitch (what/stack/problem), architecture diagram, quickstart, evidence philosophy
- [ ] **Video: 110 seconds, hard law** — 15s problem → 45s live demo → 30s Critic rejection (money shot) → 20s architecture + multilingual. No third-party trademarks/logos, no unlicensed music. Public URL (YouTube unlisted is fine — link must be public)
- [ ] Repo goes **public**; showcase site if time allows (domain from Phase 0)
- **Done when:** submission package complete per task.md checklist.

## Phase 5 — Submit (Oct 27)

- [ ] Submit on Innovation Studio by **evening PKT** (deadline = Oct 28 ~11:59 AM PKT; never deadline-day heroics)
- [ ] Pitch text: what was built, Microsoft/Azure stack used, problem solved — one paragraph, no fluff
- **Done when:** confirmation screenshot in #pl-hackathon.

## Scope law (cut order, first to go)

1. Showcase site (repo README carries launch) → 2. Extra languages beyond UR/AR → 3. What-if simulation → 4. Recap export formats (one format ships) → 5. NEVER cut: Critic loop, recovery demo, video, submission buffer.

## Standing risks

- **MatchMind (126341)** claims our EN/UR/AR trio on Agent Framework — depth + recovery beat them; watch after weekend detail pass
- Azure $100 ceiling — Foundry token burn is the risk; cap demo match length, cache aggressively, meter from day one
- Dataset unknown until Resources tab check — generator path is the default plan (pillar v of the brief explicitly invites synthetic dataset creation)
