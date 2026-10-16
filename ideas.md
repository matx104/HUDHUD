# IDEAS — Solution Options

> Status: shortlist stage. Final pick gates on (a) the Challenge-brief dataset schema — still unread — and (b) which prize lane we aim the architecture at. All ideas re-use **patterns** from existing projects (see projects.md); "newly built project" means new repo + new code, never old repos dressed up.

## Idea 1 — MatchRCA: "the 90-minute incident" ⭐ WAZIR's position

Treat the match as a production incident. A detection engine (SOCIRIS/Enterprise-Monitor pattern) baselines normal play and fires severity-ranked **live alerts during the match** — momentum breaks, chance-quality spikes, tactical deviations. Post-match: an auto-drafted **RCA per key moment** — what happened, why it mattered, causal chain, cited events. A **Critic agent** rejects any narrative claim lacking event evidence. Explainable by construction.

- **Covers:** explainable intelligence ✅ · real-time ✅ · automated recaps ✅ (RCA report) · personalized ⚠️ (via depth toggles)
- **Problem solved:** every football org below the top flight — academies, lower leagues, schools — generates event data with zero analyst budget. "The analyst for the 99%."
- **Prize lanes:** Grand + Multi-Agent + Enterprise (strong)
- **Risk:** detection quality depends heavily on dataset schema
- **Arsenal reuse:** SOCIRIS detection pattern · Enterprise Monitor correlation→narrative · Phish-Wiz report pipeline · Court Critic pattern

## Idea 2 — Ask the Match: cited Q&A over one match

RAG chat over a full match corpus (CV "Ask MAT" pattern): "Why did we lose the midfield?" → answer citing exact minutes and events, depth toggle (casual fan / tactical nerd), native EN/UR/AR. Personalized by construction.

- **Covers:** explainable ✅ · real-time ❌ (post-match) · recaps ✅ · personalized ✅✅
- **Problem:** fans get WHAT happened, never WHY — and non-English fans get translated scorelines, not narrative. Two of the brief's four verbs in one artifact.
- **Prize lanes:** Grand + Foundry (strong)
- **Risk:** post-match-only weakens the "real-time" verb; pair with a live layer or fold into Idea 1
- **Arsenal reuse:** CV Ask-MAT RAG+citations · QALAM BŪMA adaptive depth · native Urdu/Arabic

## Idea 3 — The Second Screen (ARENA pattern)

Live synthetic match streams; fans join on phones; an AI narrator reacts to match events AND crowd sentiment; mid-pressure prediction votes; post-match recap personalized to each fan's engagement. Studios/streaming platforms = the named audience.

- **Covers:** explainable ⚠️ · real-time ✅✅ · recaps ✅ · personalized ✅✅
- **Problem:** studios want second-screen engagement at scale
- **Prize lanes:** Grand + Cloud-Native (strong)
- **Risk:** heaviest build — most moving parts, weakest fit for a solo 9-day window; explainability gets diluted by spectacle
- **Arsenal reuse:** ARENA Socket.IO rooms + crowd simulator · QALAM personalization

## Idea 4 — Chalkboard: the coach's debrief

Post-match tactical debrief: pattern detection → auto-annotated 2D pitch chalkboard → adaptive drill suggestions → exportable PDF report. Coaching-staff customer.

- **Covers:** explainable ✅ · real-time ❌ · recaps ✅ · personalized ✅ (role-based)
- **Problem:** coaching staff at academies get data but no debrief tool
- **Pranky lanes:** Enterprise (strong)
- **Risk:** PDF/pitch-viz build cost; live verb missing
- **Arsenal reuse:** OMNI-GRC report DNA · QALAM BŪMA adaptive quizzing (drills)

- **Fix (typo caught in review):** prize lanes — Grand + Enterprise.

## Idea 5 — Scouter: opposition recon as a pentest

"Recon the enemy like a pentester": ingest N opponent matches → threat-model the opposition — attack vectors, exploitable weaknesses, recommended countermeasures. Security-brained judges grin; football judges may read gimmick.

- **Covers:** explainable ✅ · real-time ❌ · recaps ⚠️ · personalized ✅ (coach-view)
- **Prize lanes:** Multi-Agent (strong)
- **Risk:** highest concept risk; hinges on multi-match dataset access
- **Arsenal reuse:** QROWLER scanner DNA · threat-model format · Phish-Wiz campaign logic

## The fusion (current lean) — 1+2 on a multi-agent spine

**Scout → Narrator → Critic → Localizer, orchestrated by Microsoft Agent Framework:** live alert feed during the match (Idea 1) + "Ask the Match" cited chat + recap export after it (Idea 2), EN/UR/AR native. ARENA's crowd simulator reserved as demo garnish only if the core lands early. One build covers all four brief verbs and aims Grand + Multi-Agent + Cloud-Native simultaneously.

- **Why this shape:** the judges' multi-agent criteria (distinct roles, shared state, handoffs, failure recovery, single-agent-impossible outcome) is the Sovereign Court pattern in football jerseys — a pattern the Monarch runs in production with ten minds daily
- **Off-ramp:** Idea 3 if demo-spectacle outweighs rubric balance after the dataset lands; collapse the Azure footprint (Foundry agents + light frontend) if credits run thin

## Decision gates (in order)

1. **Challenge-brief dataset schema** (Monarch pastes next login) → picks between fusion / Idea 2 lean / Idea 3
2. **Azure credit status** → picks Container Apps vs. lightest footprint
3. **Name + domain** (project-names.md) → after solution shape is known
4. **Oct 18 build-start gate** → architecture locks
