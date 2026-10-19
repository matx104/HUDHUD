# PLAN — Build Plan (Oct 18 → Oct 27)

> The calendar is law. Every phase has a definition of done; when a phase overruns, cut from the bottom of its scope list — never borrow from the next phase's first item (video + submission are untouchable).

## Phase 0 — Weekend intel (Oct 17–19, Monarch's Playwright session)

- [x] **WATCHED (2026-10-18, via transcript; notes in docs/reference/reactor-27536.md): Reactor session "Build AI-powered soccer insights apps with AKS and ACA"** — <https://developer.microsoft.com/en-us/reactor/events/27536/> — aired Oct 14 (recording embedded on page), Brian Benz, part of the hackathon's own series. Reference architecture for deploying AI apps **and agents on AKS + ACA** with PL-inspired scenarios (play styles, counterattacks, performance patterns) — *"practical guidance attendees can extend into their hackathon projects."* This is Microsoft showing the Cloud-Native lane's expected shape — watch before architecture lock. Also check the **Series Page** link there for sibling episodes
- [ ] Detail pass on the 18 HIGH-tier projects (inspiration.md list) — what they promise vs. what they show; update threat tiers — **DEFERRED 2026-10-17:** automated browsing stopped at the gallery sign-in. Monarch reviews the 18 by hand via the local-only review page `site/review/` (gitignored, never deployed; "Copy notes as Markdown" brings the notes back)
- [ ] Sharpen the differentiation sentence (inspiration.md §Differentiation memo) against what the top 10 actually build — gated on the detail pass
- [ ] Check platform Resources tab for a sample dataset / schema (if one exists, it replaces the generator in Phase 1) — **DEFERRED** to the Monarch's manual pass; generator built meanwhile, so a platform schema would become an adapter, not a rewrite
- [x] Pick name — **HUDHUD** (Monarch, 2026-10-17; story in brand.md, set in `site/config.js` + `court/config.py`)
- [x] **Domain: hudhud.com.pk** (bought 2026-10-19 at PKNIC; live the same morning). Cloudflare zone on the Free plan via the `cf` CLI: the showcase site at the apex on GitHub Pages (DNS only, GitHub's certificate, HTTPS enforced; matx104.github.io/HUDHUD redirects), `www` → the apex, `studio.hudhud.com.pk` → a Cloudflare 307 redirect to the studio's Azure address (Azure refuses custom domains on an express environment), SPF `-all` + DMARC `reject`. `siteUrl`, the head, sitemap, robots, the social card and the public studio links follow; MCP and the Control room keep the Azure address (docs/azure.md)
- **Done when:** differentiation memo v2 written, name+domain owned.

## Phase 1 — Architecture lock + skeleton (Oct 18–20)

- [x] Activate Azure for Students ($100 credit — the ceiling, not the budget) — done 2026-10-18 (subscription a849f7b9…, spending limit on; `scripts/az`)
- [x] **Synthetic match event generator** — `packages/event-schema` (2026-10-17). Deterministic per seed; calibrated over 100 seeds to ~3.0 goals, 78.5% pass completion, 29 shots, ~320 pressures, 46 tackles per match. Emits hidden ground-truth *momentum spells* (never streamed) so Scout detection can be scored. JSON Schema committed for the web side
- [x] Agent spine — Orchestrator + Scout + Narrator + Critic + Localizer on Agent Framework 1.22 workflow (see docs/adr/0001). Shared `MatchState`, typed handoff contracts. Offline backends first (2026-10-17); the Foundry Narrator and the UR/AR Localizer since 2026-10-18
- [x] Repo scaffold: `apps/api` (package `court`), `packages/event-schema` (package `match_events`); CI from first commit. `apps/web` deferred to Phase 2 (nothing to render until the cue stream is real)
- **Done when:** one synthetic match flows end-to-end Scout→Narrator→Critic→console, with tests green. — **MET 2026-10-17** (offline backends): `make demo`, 48 tests green

## Phase 2 — Core build (Oct 21–23)

- [ ] Scout: live pattern detection — momentum swings, chance quality (xG-style), pressure shifts, control-vs-chaos index; severity-ranked live alert feed
  - [x] **Momentum, measured (2026-10-18, ADR 0002):** baseline-relative completion + final-third rate, held 3 min; scored against hidden ground truth by `make eval`. Sure-call operating point (Monarch): precision 62% / recall 26% on unseen seeds, vs 36% / 69% before. Momentum demo match: **seed 21**
  - **Eval finding (2026-10-17, seed 7):** only 1 of 5 momentum alerts overlaps a true spell. All three true spells were the away side's, yet 4 of the 5 alerts went to the stronger home side. The Scout reads *relative* dominance, so it reports a stronger team's baseline as momentum. Fix: baseline-relative (anomaly) detection, i.e. each side vs its own match-to-date rate (the SOCIRIS pattern). Score precision/recall against `GroundTruth.spells` over N seeds
- [x] **Critic momentum evidence rule** (2026-10-18, ADR 0002): the side's own shots and final-third passes, inside the claimed spell, at least three; `tests/test_momentum_rule.py` (4 tests). Live on Foundry, seed 21: all 9 alerts aired, both momentum calls included, $0.0070
- [x] Narrator: live tactical narrative + key-moment explainers (the "why", cited to events) — the template and Foundry narrators (ADR 0003), every line cited and checked
- [x] **Azure Phase A (2026-10-18):** Foundry resource `hudhud-foundry` and project `hudhud` in UAE North, `gpt-5-mini` and `gpt-4.1-mini` deployed (primary and backup chosen by evaluation, ADR 0005), Entra-only (docs/azure.md)
- [x] **Foundry Narrator (2026-10-18, ADR 0003):** `gpt-5-mini` writes the line from a fact sheet, `gpt-4.1-mini` takes over on failure; the Critic's new grounded-numbers check rejects any number code didn't compute; token meter. First live match: 7 verified cues, $0.0066
- [x] **The rules' feature list (§4.1 ii)** (2026-10-18, ADR 0008): the great-pass moment (0.8 a match), pass quality and shot speed in goal and chance lines, every number asserted and recomputed; player tags with threshold badges on every cue
- [x] **Personal modes (§4.1 i e):** favourite club, favourite player, player-focus, single-metric (2026-10-19, court/personal.py, the studio's "Make it yours")
- [x] **Receipts on every cue** (2026-10-18; Reactor 27536): `Cue.receipt`: the writer and its spend from the narrator's per-alert ledger, numbers checked from the Critic's verdict, facts recomputed and events cited from the claim, alert-to-air time from the Orchestrator. In the console, the audit trail, the alert spans and two workbook tiles. Live: median 3.6 s alert to air, ~$0.0007 a cue
- [x] **Narrator eval, "evaluation decides which model serves"** (2026-10-18, ADR 0005): rule committed before the run; seeds 60–64, 50 alerts: both 100% first pass, 0 invented numbers; gpt-4.1-mini 1.3 s median vs 3.7 s, $0.00023 vs $0.00077 a cue → **gpt-4.1-mini is primary**. Next run: a harder set (overreach rewrites, UR/AR) under the same rule
- [x] **"What this data can't tell you"** (2026-10-19: the site's limits chapter, the studio's opening slate) on the site and in the UI: momentum precision, synthetic clubs and players, no video
- [x] **Counterattack and high-press alerts** (2026-10-19: 0.6 and 1.9 a match, a Critic rule each; UR/AR headline words await the owner's review) (overview themes): transitions after a won tackle or interception, press efficiency from pressure events
- [x] **Realism report** (2026-10-19, `make realism`, docs/realism.md, the site's data chapter: goals 2.98 vs 2.77 real, draws in line, home edge smaller, 0-0 too rare at 2.5% vs 7.7%) (judging: "optimized synthetic data creation"): compare the generator's scorelines with real international results (goals per match, home-win and draw rates, scoreline frequencies). Source: the international results dataset by martj42 (Kaggle/GitHub, public domain), suggested by the Monarch 2026-10-18. **Benchmark only, never product data** (rules §4.7): downloaded locally with attribution, never committed; only our computed comparison is. Results-level only: it can't check event volumes
  - Copy bug seen in the seed-7 run: the momentum template pluralizes blindly ("1 box entries", "1 shots")
- [x] **Critic: the moat — adversarial verification.** Every claim must cite event evidence; rejections visible in UI with reasons; rewrite loop — the workflow's rewrite edge, the studio's Critic's desk, the stress test
- [x] Overlay cue stream: timed, machine-readable JSON (broadcast-renderer ready) — the platform's rendering-partner lane — `Cue` (priority, ttl_s, evidence, receipt, player tags) over Server-Sent Events from the studio
- [x] Personalization: analyst mode vs casual fan mode; club/player focus; preference drives both content AND depth (personal modes, 2026-10-19)
- **Done when:** live demo runs one match end-to-end in the UI with visible evidence links + at least one on-screen Critic rejection.

## Phase 3 — Differentiators + polish (Oct 24–25)

- [x] **Failure recovery demo (0/150 competitors claim it):** (2026-10-18: the studio's off-air switch; the Orchestrator degrades to detection-only cues and says so) kill an agent mid-match on camera → orchestrator detects, retries/reassigns, broadcast never drops; surfaced as a feature, not a footnote
- [x] **Multilingual** (2026-10-18, ADR 0009): Urdu and Arabic translated from the verified line under the same law (no invented number, names kept); refused translations air in English; the English original rides along. **Signed off by the Monarch for production, 2026-10-18** (docs/review/ur-ar.md)
- [x] Automated recap: post-match report, evidence-linked, exportable (2026-10-19, court/recap.py: every written line through the Critic with hindsight; HTML, prints to PDF; `court recap`, the studio at full time, site/recap/seed-21.html, the kit's "4 Sample match")
- [x] Observability: agent traces, token/cost meter vs the $100 ceiling (the day-job flex) — 2026-10-18, the control room below
  - Application Insights + Log Analytics + Foundry tracing; a HUDHUD workbook with the charts; a **local-only control room** page in the site whose buttons open the Azure portal views (cost, budget, app health, AI usage, AI logs) for the demo recording. Public site never shows it: the links carry subscription and tenant IDs
- [x] **MCP server** (2026-10-18, ADR 0007): the Critic as five read-only MCP tools (`list_matches`, `match_events`, `match_stats`, `match_moments`, `verify_claim`); stdio for Copilot (`hudhud-critic`), streamable HTTP at the studio's `/mcp/` (`hudhud-critic-live`). Outside callers can't vouch for their own numbers. Next: an audit record per tools/call
- [x] **The studio** (2026-10-18, local): `court/server.py` + `court/studio/` streams a match as Server-Sent Events: scoreboard and shot map, the on-air feed with a receipt per cue, the Critic's desk (red cards, the struck-through claim, reasons and the Critic's detail), a switch that takes the narrator off air (recovery on camera), a stress test that corrupts 1 in 4 drafts, join from a chosen minute (earlier alerts detected, not narrated). Caps: model matches per day, concurrent streams. `make studio`
- [x] **The wall** (2026-10-19, owner's call): the studio is owner-only, through judging too, behind Cloudflare Access at studio.hudhud.com.pk (email one-time code) with mcp.hudhud.com.pk for MCP clients (service token); an edge Worker carries both to Azure, and the studio refuses anything Access didn't sign, so its Azure address is closed too (docs/azure.md). Judges get the video, the screenshots and `make studio-offline`. The Control room lists every address
- [x] **Judge-accessible live demo (rules §4.8)** (2026-10-18; private since 2026-10-19, above): the studio on Azure Container Apps (`hudhud-studio`, express environment, UAE North), image in `hudhudstudio` (ACR Basic), signing in as `hudhud-studio-id` with four least-privilege roles and no keys. Verified in the cloud: gpt-4.1-mini narrated, the Critic refused the stress test's corrupted drafts, the audit trail kept every record. Public link on the showcase site. `scripts/deploy-studio` ships a commit. Keep it running through **Nov 10**; credit expires Nov 13
- [ ] **"Ref's call" cue** (roadmap.md bridge item, **cut first**, only if Phase 2 lands by Oct 23): Scout flags a foul tackle → Narrator states the likely decision → Critic checks it against the evidence under a lenient/standard/strict profile
- **Done when:** recovery demo + trilingual output + recap all work in one run.

## Phase 4 — Ship kit (Oct 26)

- [ ] README: pitch (what/stack/problem), architecture diagram, quickstart, evidence philosophy
- [ ] **Video: 110 seconds, hard law** — **host: YouTube, the Monarch's channel @matx104** (being set up 2026-10-19; the video link joins the site's `videoUrl` and the media kit once it's up) — the kit is ready (2026-10-18): `docs/video.md` (rules, checklist, a 1:52 shot list with voiceover, the description) and one-click takes on #/control (English, Urdu, Arabic presets). The Monarch records. — 15s problem → 45s live demo → 30s Critic rejection (money shot) → 20s architecture + multilingual. No third-party trademarks/logos, no unlicensed music. Public URL **on YouTube, Vimeo, Facebook Video or Youku** (official rules §4; a Drive link doesn't count for the submission). The master copy goes in the media kit: `scripts/drive_kit.py --video`
- [ ] Repo goes **public**; showcase site if time allows (domain from Phase 0) — **scaffold started 2026-10-17:** `site/` with an evidence-chain hero from a real seed-7 run (CI drift-checked). **Live 2026-10-17** at matx104.github.io/HUDHUD: Pages source = GitHub Actions, `pages.yml` deploys only `site/` on every push touching it (repo stays private until submission). **2026-10-18:** rebuilt as a hash-routed SPA (problem, goal, how, recovery, data, why, roadmap, name, who) with SEO tags, OG card, icons. At submission: flip `repoPublic` in `site/config.js` (shows the Code links); on domain purchase: change `siteUrl` + the `<head>` copies (tests/site fails until they agree)
- **Done when:** submission package complete per task.md checklist.

## Phase 5 — Submit (Oct 27)

- [ ] Submit on Innovation Studio by **evening PKT** (deadline = Oct 28 ~11:59 AM PKT; never deadline-day heroics)
- [ ] Pitch text: what was built, Microsoft/Azure stack used, problem solved — one paragraph, no fluff
- **Done when:** confirmation screenshot in #pl-hackathon.

## Decisions from the official rules (settled 2026-10-18)

- **GitHub Copilot agent mode:** the Monarch builds with it. Done: `.github/copilot-instructions.md` (the laws, the commands, Azure guardrails) and `.vscode/mcp.json` → `scripts/azure-mcp` (Azure MCP Server 2.0.5, pinned, signed in as the project CLI; verified it sees the student subscription, not the Windows account). Next: our own MCP server (the Critic as a tool) in the same file, so Copilot can have a claim checked
- **Microsoft Fabric:** out of scope (2026-10-19). Considered for analytics over the audit trail, by mirroring the free-tier Cosmos DB account into OneLake (ADR 0004); open to it as the project grows
- [x] **Audit trail** (2026-10-18, ADR 0004): `court/audit.py` tees the sink, writes off the hot path, a failing store costs the trail not the broadcast (4 tests); `--audit cosmos` → `hudhud-audit` (free tier, Central India, keys off, capped at 1,000 RU/s). First live run: 11 records, read back by query
- [x] **Control room** (2026-10-18): `hudhud-logs` (0.1 GB/day cap) + `hudhud-insights` (keys off); OpenTelemetry from the court (match request, alert spans with outcome and rejection codes, Agent Framework's model spans with tokens); the HUDHUD workbook (`make control-room`, every query run against real data first); the local-only `#/control` page of 20 portal links. Owner to click through each link before recording. First finding: 77% of gpt-5-mini's output tokens are hidden reasoning
- **Fabric mirror** of the audit container: out of scope (2026-10-19), not built. The route for SQL and Power BI over every match if the project grows (ADR 0004, docs/azure.md)
- [x] **Media kit on Google Drive** (2026-10-18): a public folder (anyone with the link can view, owner hidden) with "1 Demo video", "2 Azure screenshots", "3 Brand kit", a Read me PDF and the cover; built and synced by `scripts/drive_kit.py` from `kit/` and what the site already shows. Linked from #/about and #/control (`kitUrl`)
- [x] **Azure screenshots** (2026-10-19): eight from the portal (home, resource group, workbook, Foundry, cost, studio, the audit trail's free tier and activity), cropped below the account bar, OCR-redacted, each checked by eye, on #/control and in the kit. Held back: the application map (taken on "Last hour", it showed only a telemetry endpoint). A retake on "Last 24 hours" after a match, and Foundry's model deployments list, would add to it
- [x] **Showcase site: build log and credits pages** (2026-10-18): `#/log` (live vs next, with a receipt for the seed-21 Foundry match) and `#/credits` (data, the Reactor session, libraries and licenses, fonts, tools, the name's source)

- [x] **History cleaned before going public** (2026-10-18): the scouting notes (`inspiration.md`, `inspiration-projects.json`) and a fragment of the owner's directory name (once in `scripts/redact.py`) are gone from every commit, by git-filter-repo. The final tree is unchanged; every commit hash changed, and ADR 0005's citation follows its commit. A bundle of the old history is kept off the repo, on the owner's machine

## Scope law (cut order, first to go)

0. "Ref's call" cue (roadmap bridge) → 1. Showcase site (repo README carries launch) → 2. Extra languages beyond UR/AR → 3. What-if simulation → 4. Recap export formats (one format ships) → 5. NEVER cut: Critic loop, recovery demo, video, submission buffer.

## Standing risks

- **MatchMind (126341)** claims our EN/UR/AR trio on Agent Framework — depth + recovery beat them; watch after weekend detail pass
- Azure $100 ceiling — Foundry token burn is the risk; cap demo match length, cache aggressively, meter from day one
- Dataset unknown until Resources tab check — generator path is the default plan (pillar v of the brief explicitly invites synthetic dataset creation)
