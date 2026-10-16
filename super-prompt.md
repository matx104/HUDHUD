# SUPER PROMPT — Claude Code Master Brief (paste-whole, this repo)

> This file is the single source of truth for any Claude Code session building this project. Read every file it names before writing code. Work autonomously — do not stop to ask questions the repo already answers. When this prompt and reality conflict, trust the repo files, then flag the conflict in your summary.

## MISSION

Build a **multi-agent football match-intelligence system** for the Microsoft × Premier League "Inside the Game" hackathon: turn a live stream of synthetic football events into explainable, evidence-verified match intelligence — live narratives, broadcast-ready overlay cues, automated recaps — personalized per viewer (analyst vs casual fan, club/player focus) and multilingual (native EN/UR/AR). **Solo entry, one repo, submit Oct 27 11:59 PM PT.** Working name: placeholder (`pl-hackathon`); final name lives in project-names.md once chosen — do not hardcode the name anywhere user-visible; read it from one config/constant.

## READ FIRST (order matters)

1. `task.md` — the official ask: rubric (5 × 20%), prize categories, HARD rules (video <2:00, public repo, synthetic data only)
2. `inspiration.md` + `inspiration-projects.json` — the 150-project competitive field: what's contested (evidence claims ×29), what's open (**failure recovery — 0/150 claim it; enterprise posture — 0/150**), and the naming intel (never Match*/Pitch*/Touch*)
3. `ideas.md` — the fusion architecture (Idea 1+2 on a multi-agent spine) and decision gates
4. `plan.md` — the phase plan with definitions of done and the cut order
5. `brand.md` — identity system, palette, voice, video law
6. `project-names.md` — verified name candidates (do not invent new names; pick only from here when asked)
7. `projects.md` — the Monarch's reusable-pattern arsenal (patterns, never old-repo code)

## THE ARCHITECTURE (locked unless plan.md says otherwise)

**Five agents, Microsoft Agent Framework, Foundry-hosted:**
- **Orchestrator** — routes events, owns shared match state, **detects agent failures and retries/reassigns without dropping the stream** (this is a scored feature — judges' criteria name "recover from failures" explicitly, and 0/150 competitors claim it)
- **Scout** — live pattern detection: momentum swings, chance quality (xG-style), pressure shifts, control-vs-chaos index; severity-ranked alerts
- **Narrator** — live tactical narrative + key-moment explainers; every claim carries event citations (minute + event ids)
- **Critic** — adversarial verifier: claims without sufficient event evidence are REJECTED with reasons, sent back for rewrite; rejections are first-class UI artifacts, not logs
- **Localizer** — EN/UR/AR output at native register (not translationese); personalization depth (analyst/casual) applied here too

**Pipeline shape (the brief's five stages, mapped):** ingest (synthetic stream) → interpret (Scout) → explain (Narrator+Critic) → render (overlay cue stream: timed machine-readable JSON + web studio UI) → personalize (modes, club/player focus, language).

**Evidence law (the moat):** every narrative claim links to its supporting events; the Critic's rejection of an unevidenced claim is the demo's money shot. 29/150 competitors claim evidence — we execute it live and frame it as an audit chain.

## HARD CONSTRAINTS

- **Azure ceiling: $100 (student credit).** Meter token/cost from day one; cache aggressively; demo matches capped in length. No service without a named justification against the rubric.
- **Synthetic data only** — no real PL data, no club names in output surfaces, no third-party trademarks in video/assets.
- **New code only** — patterns from projects.md are inspiration; no copying from existing repos.
- **Video: 110 seconds** (15 problem / 45 demo / 30 Critic rejection / 20 architecture+multilingual), royalty-free audio only.
- **Main branch only; small conventional commits** (`feat:`, `fix:`, `docs:`); every push verified (`git fetch` + HEAD == origin/main).
- **Tests from the first commit.** The repo's CI must never be red at phase end.
- Non-English strings (UR/AR): mark for owner review — never trust the agent's own translation instincts as final.

## THIS WEEKEND'S SESSIONS (Oct 17–19) — definition of done

1. **Playwright detail pass on the 18 HIGH-tier projects** (ids in inspiration.md): for each, record stack-claims vs. visible substance; update `inspiration-projects.json` tiers; sharpen the differentiation memo to v2
2. **Platform Resources check:** sample dataset or schema? If yes — replace the generator task in plan.md Phase 1 and record the schema in `task.md`
3. **Name + domain:** Monarch picks from project-names.md, buys the domain (cheap TLDs; re-verify RDAP day-of); set the name constant
4. Kick Phase 1 skeleton if time remains after 1–3 (Azure student activation is Monarch-manual — see MANUAL PREREQS)

Report at session end: what was verified, what changed in which file, what's blocked. Commit everything with push-verify. — WAZIR 🦁
