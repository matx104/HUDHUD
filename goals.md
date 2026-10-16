# GOALS — The Grand Slam Doctrine

> **Declaration:** We intend to win ALL SIX categories. Solo entry, one build, six lanes. This file maps every award to the features that win it — if a feature doesn't serve a lane, it's cut; if a lane lacks a feature, the gap closes before build ends. The intention goes **public on the showcase site**: stated plainly, backed by the artifact.

## The doctrine in one line

**Build the system the rubric describes, then execute the two things nobody else in the field of 150 even claims — adversarial verification made visible, and failure recovery made deliberate.**

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

> *"We declared for all six categories before the deadline — not because the sweep is likely, but because building to win six forces the discipline of six. Every feature on this site maps to a lane in goals.md in our repo. Judge us against our declaration."*

Honest-bravado tone: state the sweep, show the mapping, invite audit. (final copy at showcase build — brand.md voice)

## Non-negotiables (cut-order floor, mirrors plan.md)

1. Critic rejection loop, visible in UI
2. Failure-recovery demo, on camera
3. 110-second video law
4. Submission buffer (Oct 27 evening PKT, never deadline-day)

## Kill criteria (honesty clause)

If by Oct 24 the core loop isn't demoable end-to-end, we narrow the declaration publicly to the two lanes we can defend (Multi-Agent + one other) — **a narrowed claim we hold beats a sweep we can't.** Declaring six is ambition; holding what we declare is the brand.
