# Reactor 27536: "Build AI-powered soccer insights apps with AKS and ACA"

> Microsoft Reactor, streamed live 2026-10-14 (Pacific), 63 minutes. Speaker: Brian Benz, Principal AI Advocate, Microsoft.
> The only session in the hackathon's Reactor series, "Inside the Game: Developer Hackathon" (S-1709, aka.ms/PremierLeagueHack). The series page also features a project, "The Synthetic Match Insights Engine for Premier League Studio" (real-time insights, narratives and recaps on Azure).
> Video: https://www.youtube.com/watch?v=EQ187ohgCbo · Reference app: aka.ms/football-results-dashboard
> Watched through its transcript on 2026-10-18 (plan.md, Phase 0). The full transcript is local and
> gitignored (`reactor-27536-transcript.local.md`); these are our notes, in our words.
> **New code only:** the reference app is inspiration, never a source to copy (rules §4.6, §4.11).

## Chapters (from the video description)

| Time | Chapter |
|---|---|
| 0:00 | Introduction and housekeeping |
| 1:13 | Hackathon details and goals |
| 2:56 | Live demo of the football results dashboard |
| 4:49 | Exploring 150 years of international football data |
| 8:19 | Agenda |
| 9:17 | Reference architecture (AKS and ACA) |
| 11:29 | Data flow and ingestion |
| 12:33 | **Deterministic code vs. Microsoft Foundry logic** |
| 14:43 | Security and Microsoft Entra ID |
| 18:01 | The Azure resource group and its components |
| 20:41 | Data sources and handling in the repository |
| 27:06 | Data reconciliation and naming |
| 31:13 | AKS versus ACA |
| 38:03 | Scaling, revisions and rolling updates (and "every answer carries its receipts", 38:39) |
| 42:41 | Building the app with GitHub Copilot |
| 43:40 | The generation prompt |
| 57:00 | Final thoughts, resources and Q&A |

## What he built

A football Q&A dashboard over open match data, built with GitHub Copilot in about a day. One set of
container images (web, insights, an ingest job) runs three ways side by side: locally under Docker
Compose, on Azure Container Apps and on AKS. The UI shows which platform served each answer.

- **Data:** public-domain international results from Kaggle plus development indicators. The data is
  kept out of the repo: an ingest job builds a curated copy into Blob Storage and DuckDB. Attribution
  is on the front page. Half the work was reconciling team names that changed over 150 years.
- **The split of labour:** deterministic code computes every number, table and chart. A Foundry model
  chooses which read-only tools to call, writes a grounded narrative, and says when a question is out
  of scope ("this data covers national teams, not club football, and has no counterattack data").
- **The request path:** question, plan, schemas, compute; facts come back with **evidence IDs**; the
  model reasons and returns JSON; a basic sanity and coherency check runs; the answer is displayed.
- **Limits:** at most 6 tool calls, 1,200 output tokens and 45 seconds per answer; conversation
  storage is off.
- **"Every answer carries its receipts":** live and grounded status, "five numbers were checked", the
  model, latency (5.8 s), output tokens (254) and an estimated price. An evidence ID for every
  number, charts built from tool data, a **"what this data can't tell you"** panel, and an in-app
  trace view (OpenTelemetry to Application Insights).
- **"Evaluation decides which model serves":** grounding, tool selection, limitations and framing,
  live narratives, content-filter blocks (zero) and latency. The fast model won: the stronger
  reasoning model was slower and no better.
- **Security:** Entra ID everywhere, a user-assigned managed identity per service (workload identity
  on AKS), no keys, endpoints limited to his IP. Locally, a short-lived token refreshed every 15 minutes.
- **AKS vs ACA, his view:** ACA for disposable dev and test (built-in ingress, HTTP-rule autoscale,
  revisions with traffic weights); AKS for full lifecycle control (gateway API, rolling updates,
  pinned versions). Performance was comparable for this app.
- **How it was built:** a 498-line generation prompt, iterated a dozen times, then GitHub Copilot in
  agent mode ran it (with Claude Opus 5.5, at max effort). Presenter notes and the env file stayed in
  ignored local files. About a day in all.
- **From the Q&A:** asked whether real data is allowed when the hackathon requires synthetic data,
  he wasn't sure and deferred to the organizers. The hackathon provides no Azure credits.

## Where HUDHUD already goes further

| His dashboard | HUDHUD |
|---|---|
| A grounding check that rejects any number the model writes that the tools didn't return (the repo shows it's stricter than the talk's "sanity check") | The same number check, plus an adversarial **Critic** that recomputes each assertion from raw events as of the claim's moment, rejects on screen and sends the claim back for a rewrite |
| Q&A after the fact | Live: claims made *during* a match, checked against only the events that had happened yet (a citation from the future is rejected) |
| Real open data; legality unclear to the presenter | **Synthetic by design**, as the rules require, with hidden ground truth that scores the Scout (`make eval`) |
| One agent with tools | Five agents with typed handoffs, a hot and a warm path, and failure recovery that keeps the broadcast going |

## What we take from it (in plan.md)

1. **Receipts on every cue:** verified or detection-only, numbers checked, model, latency, tokens,
   estimated cost and evidence IDs. Our token meter feeds it.
2. **"What this data can't tell you":** state limits plainly on the site and in the UI. For example,
   momentum calls are right 62% of the time on unseen matches, and every club and player is invented.
3. **Evaluation decides which model serves:** a narrator eval that runs `gpt-5-mini` and
   `gpt-4.1-mini` over the same alerts and scores first-attempt pass rate with the Critic, grounding
   failures, latency and cost. A Foundry story, measured.
4. **Traces in the product:** OpenTelemetry to Application Insights, linked from the local control
   room for the video.
5. **Hard per-request limits:** timeouts, token caps, bounded retries (the Foundry narrator has a 30 s
   timeout and a backup model).
6. **One image, more than one platform:** run the same images on Container Apps, and consider AKS
   side by side for the cloud-native category if the budget allows.
7. **His IP allow-list doesn't fit us:** rule 4.8 requires judges to reach a working demo through
   Nov 10. We stay public and protect the bill with rate limits and the spending limit instead.

## The presenter's other public sessions (October 2026)

From the presenter's public posts, three ideas that sharpen ours (`plan.md`):

- **"Who can call this MCP tool?"** (MCP Dev Summit Toronto, Oct 6): MCP authorization at
  `tools/call`, and an audit record tying each call to the user, client, resource, policy and
  result. When the Critic becomes an MCP tool, each call gets that record in the audit trail.
- **A "referee" engine for coding-agent sandboxes** (Reactor, Oct 13): a coding agent's fixes run
  in isolated Container Apps sandboxes, and a referee compiles, tests and judges each one. A fix
  that passed every test but tried to send a secret out was blocked, logged and disqualified. The
  same stance as our Critic: passing isn't enough when the evidence says otherwise.
- **Observability from laptop to cluster** (AGNTCon + MCPCon workshop, Oct 23): OpenTelemetry
  traces for every agent step, tools over MCP, the same containers from Compose to Kubernetes.

## The second dataset he used

He also used **Global Development Data (1960–2025)** by Yogesh Mishra on Kaggle (from the World
Bank's World Development Indicators, CC BY 4.0), mainly for regions and income groups and to map
country names that changed over time. The results data is **International football results from
1872 to 2026** by Mart Jürisoo (Kaggle and GitHub, CC0). HUDHUD has no countries and no real teams, so it has no use
here; it stays out, like the results data, which may only ever serve as a credited benchmark.

## The reference repo (github.com/bbenz/football-results-dashboard, MIT; studied 2026-10-18)

Read for ideas only; HUDHUD's code is its own (rules §4.6). What we take into the control room:

- **Telemetry with keys off:** the Azure Monitor OpenTelemetry distro exports to Application
  Insights with an Entra credential, the resource has local auth disabled, and prompts and
  responses are never recorded. Agent Framework's spans (`invoke_agent`, `chat <model>`,
  `execute_tool`) carry `gen_ai.*` token attributes into `dependencies.customDimensions`.
- **App attributes on the agent span:** answer status, grounding result and estimated cost, so
  one KQL query gives answers per day, the grounded share, p50/p95 latency and cost per answer.
- **A query for hidden failure:** answers that should have been live but weren't. Ours: cues that
  aired detection-only, and every `Degradation`.
- **Evaluation with a decision rule agreed before the run:** gates on grounding, tool selection,
  limitations and latency, several repeats per case because model output varies.
- **Data attribution on the front page and in the README**, with authors and licenses, and the data
  never redistributed.
