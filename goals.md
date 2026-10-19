# GOALS — The Grand Slam Doctrine

> **Declaration (revised 2026-10-19 by the Monarch):** Build and claim **every award: all six**. Nothing is narrowed: each lane is built to win and claimed as such on the site's Goal chapter ("Built to win every award"). The rules (§4.2, §8) cap what one project can take home at one Grand Prize and one Category Prize; that cap is stated once, as a fact, and is the judges' call, not a reduction of the build. One engineer: every public word is first person singular (I, my), never we or our.
>
> *Superseded (2026-10-18):* the fallback goal of Grand Prize: First Place plus Best Use of Microsoft Foundry.

## The doctrine in one line

**Build the system the rubric describes, then execute the two things nobody else in the field of 150 even claims — adversarial verification made visible, and failure recovery made deliberate.**

## The north star (beyond the hackathon)

The hackathon build is stage one. HUDHUD's end goal is an **AI fourth official**: it judges calls in a blink at a chosen strictness, shows the evidence for every decision and explains it to the crowd, while the human referee decides. The stages, gates and principles are in **roadmap.md**. Motto: **Onwards & Upwards.** For the hackathon, the vision is the declared direction, not a claim: the entry is judged on what Stage 1 ships.

## Award → Feature mapping (the build contract)

**🏆 Grand 1st (the completeness prize)**
Every lane below, integrated without seams — one match, end-to-end, polished. Judges score 5 × 20%: tech implementation (CI, tests, clean code) · agentic design (five distinct agents, real orchestration) · real-world impact (the analyst-for-the-99% story) · UX (studio UI + the 110s video) · category adherence. **Killer features:** the live Critic rejection + the one-match vertical slice done brilliantly.

**🧠 Best Use of Microsoft Foundry**
- Agents built, hosted, and orchestrated IN Foundry (Agent Framework + agent service) — not Foundry as a badge, Foundry as the factory
- Model routing with cost/quality tiers (cheap model for detection summaries, strong model for narrative) — shows platform mastery
- Deployment via Foundry flows, evals on narrative quality — "faster innovation" demonstrated, not claimed

**💼 Best Enterprise Solution**
- **The 0/150 open lane.** Production posture: auth, rate limits, cost governance ($100 ceiling metered from day one), data-retention policy, deployment guide
- The audit-chain framing: every claim → events → verdict, reviewable post-hoc = broadcaster compliance story (nothing unverified goes to air)
- Observability: agent traces, token/cost dashboards — the CISSP/observability-architect credibility, made visible

**💡 Best Multi-Agent Orchestration**
- Five DISTINCT roles with defined handoff contracts + shared match state (not five prompts in a trench coat)
- **The recovery demo — 0/150 competitors claim failure recovery:** kill an agent mid-match on camera → orchestrator detects, retries/reassigns, broadcast never drops. This alone answers the judges' criteria verbatim
- Graceful degradation levels: full → detection-only → cached-recap mode

**🎨 Best Azure Cloud-Native Integration**
- Event-driven end-to-end: event generator → Event Hubs/queue → agent pipeline (Container Apps) → overlay cue stream + web UI
- Bicep/IaC for the whole stack (Terraform brain, Azure-native hands) — deployable in one command
- Azure-monitor wiring + the cost meter; resiliency patterns visible (retries, dead-letter, health probes)

**🏆 Grand 2nd** — not a target; the fallback if Grand 1st is stolen. Same build.

## The public intention (showcase-site language, draft)

> *"We set out to win every category. The rules allow two: first place overall, and Best Use of Microsoft Foundry. Every other category is still built to its full standard, because that is what first place takes."* (live on the Goal page)

Honest-bravado tone: state the sweep, show the mapping, invite audit. (final copy at showcase build — brand.md voice)

## Non-negotiables (cut-order floor, mirrors plan.md)

1. Critic rejection loop, visible in UI
2. Failure-recovery demo, on camera
3. 110-second video law
4. Submission buffer (Oct 27 evening PKT, never deadline-day)

## Kill criteria (honesty clause)

If by Oct 24 the core loop isn't demoable end-to-end, we narrow the declaration publicly. **Met 2026-10-18:** the core loop ran end to end, live on Azure Container Apps, six days early.
