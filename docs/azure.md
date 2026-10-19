# Azure: account, credits, guardrails

> Snapshot from the portal and the CLI on 2026-10-18. Identifiers (subscription IDs, tenant) live
> in the gitignored `azure.local.md`, because this repo goes public.

**The account has two subscriptions. Only one is ours.**

| Subscription | Offer | Spending limit | For this project |
|---|---|---|---|
| **Azure for Students** | Azure for Students | **On**: stops at the credit, never bills a card | **Yes, the only one** |
| Azure subscription 1 | Pay-As-You-Go | Off: charges go to the card on file | **Never** |

`scripts/az` defaults to Azure for Students. Check `scripts/az account show` before any create.

## The account

| | |
|---|---|
| Offer | Azure for Students (spending limit on) |
| Credit | **$100**, $0.00 spent (October) |
| Credit expires | **2026-11-13** (26 days from 2026-10-18); "eligible students can renew" |
| Role | Owner of the subscription |
| Status | Active, no resources yet |
| Budget | `hudhud-credit`: $100, alerts to the Owner role at 25/50/75/90% actual and 100% forecast (created 2026-10-18) |

**Dates that matter:**
- **Submission:** Oct 27, 11:59 PM PT, which is Oct 28, 11:59 AM PKT. The plan submits on the evening of Oct 27, PKT.
- **Judging:** the hackathon runs until Nov 21, but the credit expires on Nov 13. Anything live for the judges after Nov 13 needs the renewal, or the demo has to work without Azure (the offline backends already do).
- **The spending limit cuts both ways:** it can't overspend, but when the credit runs out the subscription is disabled and everything stops. Spending the credit before the deadline would take the demo down.

## Where it runs: UAE North

The student subscription may deploy to only five regions: Central India, India South Central,
UAE North, Austria East and East Asia. Only **UAE North** offers pay-per-token model deployments
(GlobalStandard); the others offer provisioned throughput only. UAE North also has Container
Apps, Cosmos DB, Service Bus, Container Registry, Log Analytics and Key Vault, so everything lives
there. It's also the closest region to Karachi.

**Model quota on this subscription (thousands of tokens per minute, GlobalStandard):**
- `gpt-5-mini` 500, `gpt-4.1-mini` 200, `o4-mini` 100.
- Foundry open models: `gpt-oss-120b`, Phi-4, Llama 3.3/4, Mistral.
- Newer models (`gpt-5.4-mini`, `gpt-5.5` and up) are listed in the region but have zero quota for
  students.

## Resources (Phase A, created 2026-10-18)

| Resource | What | Notes |
|---|---|---|
| `rg-hudhud` | resource group, UAE North | tags `project=hudhud`, `owner=monarch`; delete it to remove everything |
| `hudhud-foundry` | Foundry resource (AIServices, S0) | **key auth disabled**: Entra ID only, nothing to leak; system-assigned identity |
| `hudhud` | Foundry project | endpoint `https://hudhud-foundry.services.ai.azure.com/api/projects/hudhud` |
| `gpt-5-mini` | deployment, model version 2025-08-07, GlobalStandard, 50K TPM | backup Narrator since ADR 0005 (primary before: as good, but 3x slower and dearer) |
| `gpt-4.1-mini` | deployment, model version 2025-04-14, GlobalStandard, 50K TPM | **primary Narrator** since ADR 0005: as grounded as gpt-5-mini, a 1.3 s median cue against 3.7 s, a third of the cost |
| `hudhud-audit` | Azure Cosmos DB for NoSQL, **free tier**, Central India | the audit trail (ADR 0004); keys disabled; total throughput capped at 1,000 RU/s so it can't leave the free tier; continuous 7-day backup (free, and required for Fabric mirroring); database `hudhud` (1,000 RU/s shared), container `audit` (`/matchId`). The Monarch's sign-in holds the built-in Data Contributor role |

Cosmos DB is in Central India because UAE North refused new accounts for high demand on 2026-10-18.

| `hudhud-logs` | Log Analytics workspace, UAE North | 30-day retention; **daily cap 0.1 GB**, which keeps it inside the free 5 GB a month |
| `hudhud-insights` | Application Insights (workspace-based) | **local auth disabled**: the exporter signs in with Entra; the Monarch holds Monitoring Metrics Publisher on it |
| HUDHUD control room | Azure Monitor workbook | deployed by `make control-room` from `infra/monitor/hudhud-workbook.json` (no IDs in the repo); a fixed GUID name, so a rerun updates it |

| `hudhudstudio` | Container Registry, Basic, UAE North | the studio's images; admin user off; pulled by the app's identity. $0.1666 a day |
| `hudhud-studio-id` | user-assigned managed identity | the studio's only identity: AcrPull on the registry, Cognitive Services User on Foundry, Monitoring Metrics Publisher on Application Insights, built-in Data Contributor on the Cosmos DB account |
| `hudhud-env` | Container Apps environment (express), UAE North | platform logs off: the app sends its own traces to Application Insights |
| `hudhud-studio` | Container App, 0.25 vCPU, 0.5 GiB, one replica | **the live demo** at https://hudhud-studio.politesand-62c3c2c4.uaenorth.azurecontainerapps.io/ ; signs in as `hudhud-studio-id` (`AZURE_CLIENT_ID`), no keys or secrets; caps of 200 model-narrated matches a day and 8 streams at once. One replica on purpose: a match's off-air switch lives in that replica's memory |

### The studio

`make studio` runs it locally (the project's CLI signs in); `scripts/deploy-studio` builds the image,
pushes it and rolls the app onto it, tagged with the commit. Cost while it runs: the registry about
$5 a month, the app about $5 a month after the free grant, models at most $0.40 a day under the cap.
Container Apps creates express environments now; they don't take Azure Monitor as a log destination,
so platform logs are off and the app's own telemetry carries the story.

### The control room

`make control-room` deploys the workbook and writes `site/data/ops.local.js` (git-ignored: the links
carry the subscription's IDs). `make site`, then open http://localhost:8000/#/control: twenty buttons
into the portal, grouped as the dashboard, money, AI at work, app health, data and everything. The
page exists only when the site is served from this machine; the public site never requests the file
(`tests/site/site.test.cjs` checks it). The deep links follow the portal's URL patterns and were not
clicked through by the agent, which never signs in to the portal; check each before recording.

`scripts/live` sends traces to Application Insights: a `match` request per run with its stats and
cost, a span per alert with its outcome and the Critic's rejection codes, and Agent Framework's
`chat <model>` spans with token counts (no prompts or model output).

The Monarch's account holds **Cognitive Services User** on `hudhud-foundry`: the Foundry project
endpoint needs `Microsoft.CognitiveServices/*` data actions. (Azure AI Developer, tried first, covers
only OpenAI, Speech, Content Safety and model-catalog actions, so the project returned 403; "Azure AI
User" isn't offered in this tenant yet. A new role took about four minutes to take effect.) Deployments cost nothing until
called. A test call on 2026-10-18 cost a fraction of a cent. `gpt-5-mini` spends hidden reasoning
tokens, so live cues set its reasoning effort to minimal.

## Free services that fit this build (from the portal's free-services page; confirm per subscription before relying on one)

| Need in our architecture | Free allowance shown | Use |
|---|---|---|
| Event queue between generator and agents | Service Bus Standard, 750 hours a month | the match event stream (Phase 3, cloud-native lane) |
| Container images | Container Registry Standard, 31 days a month | images for the agent services |
| Shared state, recaps, audit trail | Cosmos DB free tier: 25 GB stored, 400 RU/s | the claim → events → verdict audit trail |
| Static assets, exports | Blob Storage hot LRS, 5 GB | recap exports |
| Secrets | Key Vault | connection strings, keys |
| Egress | 15 GB data out | the web UI and the cue stream |

**Not on the free list:** model calls (Foundry/Azure OpenAI tokens), Container Apps beyond its own
monthly grant, Event Hubs, and log ingestion past the free tier. These spend the $100. Check exact
prices with the pricing calculator before creating anything.

## Guardrails (decided before the first resource exists)

1. **One resource group** for everything (`rg-hudhud`). Tags `project=hudhud`, `owner=monarch`. One
   command removes it all: `scripts/az group delete -n rg-hudhud`.
2. **A budget on day one** (done): $100, with alerts at 25%, 50%, 75% and 90% to the subscription Owner.
3. **Model spend is the risk** (goals.md: the $100 is the ceiling, not the budget). A cheap model
   for detection summaries and a stronger one only for narrative. Demo matches are capped in
   length, responses are cached, and token cost is metered from the first call.
4. **No resource without a named reason** tied to the rubric (super-prompt.md).

## The domain: hudhud.com.pk (Cloudflare, Free plan)

Bought 2026-10-19 at PKNIC, delegated to Cloudflare (macy and matteo.ns.cloudflare.com), managed
with the `cf` CLI. Records:

| Name | Points at | Proxy | Why |
|---|---|---|---|
| `hudhud.com.pk` | GitHub Pages: A 185.199.108-111.153, AAAA 2606:50c0:8000-8003::153 | DNS only | the showcase site; GitHub issues its certificate, which needs the name to reach GitHub directly |
| `www` | CNAME matx104.github.io | DNS only | GitHub redirects it to the apex |
| `studio` | CNAME to the container app's address | **proxied** | the edge Worker carries it to the studio, behind Cloudflare Access |
| `mcp` | AAAA `100::` (no origin: the Worker answers) | **proxied** | the Critic's MCP endpoint, the studio's `/mcp/`, behind the same Access app |
| `kit` | AAAA `100::` | **proxied** | a redirect rule (302) to the media kit on Google Drive |
| `@` TXT, `_dmarc` TXT | SPF `-all`, DMARC `p=reject` | | the domain sends no mail, so nothing may claim to |

The studio can't take the domain itself: Azure refuses custom domains on an **express** Container
Apps environment (`ExpressEnvironmentFeatureNotSupported`), and a proxied record alone can't reach
it either, since Container Apps routes by the Host header and only Enterprise plans can rewrite it.
So a Worker (`edge/`, deployed by `scripts/edge`) forwards each request to the studio's Azure address
and points Azure's redirects back at the address the viewer used. Moving the studio to a full
environment would let Azure serve the name with its own certificate.

## Foundry tracing (2026-10-19)

The Foundry project `hudhud` has a connection to `hudhud-insights` (category AppInsights, made with
`az rest` against `.../projects/hudhud/connections/hudhud-insights`), so the model calls the court
traces (Agent Framework's gen_ai spans, with tokens) also show in the Foundry portal's tracing
view, next to the deployments. Viewing them needs read access to the Application Insights
resource. The doctor checks the connection.

## The voice: Azure AI Speech (2026-10-19)

Every verified line can be read aloud (`court/speech.py`): neural voices en-GB-RyanNeural,
ur-PK-AsadNeural and ar-AE-HamdanNeural on the same Foundry resource (`hudhud-foundry`, an
AIServices account), at `https://uaenorth.tts.speech.microsoft.com`. Entra ID only: the request
names the resource and carries the token (`Authorization: Bearer aad#<resource id>#<token>`); the
studio's identity has Cognitive Services User on the resource. Settings: `SPEECH_RESOURCE_ID`,
`SPEECH_REGION`. The page asks for a line by its cue's id (`/api/sessions/<id>/speak?cue=...`),
never with text, so the voice can only say what aired. A daily budget of 150,000 characters
(about 1,000 lines) caps the cost; neural voices list at about $15 a million characters. The
doctor and `make smoke` check it.

## Running it: probes, one replica, retention (2026-10-19)

- **Health probes:** liveness every 30 s and readiness every 10 s on `/healthz` (the template,
  applied with `containerapp update --yaml`; image updates keep it). A container that stops
  answering is restarted; one that isn't ready gets no traffic.
- **One replica, on purpose.** A match's stream and its off-air switch must reach the same
  replica, since sessions live in memory, and express environments refuse sticky sessions
  (`ExpressEnvironmentFeatureNotSupported`). One replica of 0.25 vCPU holds eight concurrent
  matches (`STUDIO_MAX_STREAMS`) and a daily model budget, which is the demo's audience. Scaling
  out means a full environment with sticky sessions, or the session's controls moved into shared
  state: both are on the roadmap, not claimed.
- **Retention:** audit records expire 90 days after their last write (the container's default
  TTL, 7,776,000 s), past the judging period. Checked by `make doctor`.

## The wall: the studio is owner-only (Cloudflare Access)

Decided 2026-10-19 by the owner: the studio stays private, through the judging period too. The
rules let judges judge on the text, images and video alone (§4.8); the video shows the studio at
work, and the code, public at submission, runs the same studio on any machine
(`make studio-offline`, no Azure).

- **Access application** `HUDHUD studio` on the account's Zero Trust organisation (Free plan),
  covering `studio.hudhud.com.pk` and `mcp.hudhud.com.pk`. Two policies: `HUDHUD owner` lets in the
  owner's email address, signed in by a one-time code sent to it (24-hour sessions); `HUDHUD
  machines` (Service Auth) lets in one service token, for the smoke test, the doctor and MCP
  clients. Machines get a 401, not a sign-in page. The sign-in page shows the account's team name.
- **The service token** lives only on the owner's machine, in `~/.config/hudhud/access-token.json`
  (mode 600), read by `scripts/_azure.py`; it expires 2027-10-19. A script sends its two headers
  (`CF-Access-Client-Id`, `CF-Access-Client-Secret`) and a User-Agent of its own: Cloudflare turns
  away Python's default one. Rotate it in the Zero Trust dashboard, or by the cf CLI's
  `zero-trust access service-tokens rotate`.
- **No way around it.** With `ACCESS_TEAM` and `ACCESS_AUD` set on the container app, the studio
  checks the token Access signs for every request (`Cf-Access-Jwt-Assertion`) against the team's
  published keys, the app's audience tag and the issuer (`court/server.py`, `AccessOnly`), and
  answers 403 to anything else, so its Azure address is closed to direct visits. Nothing secret is
  stored: the keys are public, and an unknown key id refreshes them at most once every five minutes.
  `/healthz` stays open for Container Apps' probes; it says only "ok".
- **Checked** by `make doctor`: strangers are sent to sign in, the Azure address answers 403, the
  service token gets through. `make smoke` streams a match through the wall.
- **Settings take effect with an image.** On the express environment a settings-only update
  (`containerapp update --set-env-vars`) changes the revision but leaves the running container as it
  was, and `revision restart` fails (InternalServerError). Ship an image (`scripts/deploy-studio`) to
  bring new settings into force; the doctor's wall checks show when they are.
- **The Worker** builds with the cf CLI, which loads `edge/cloudflare.config.ts` with Node's own
  TypeScript support. Some distro builds of Node leave it out (this machine's did): `scripts/edge`
  then uses an official Node 24 build unpacked under `~/.local/share/hudhud/`, or `EDGE_NODE`.

GitHub Pages serves the site at the apex with HTTPS enforced; matx104.github.io/HUDHUD/ redirects
there. Set a Pages custom domain only once the name resolves to GitHub: the redirect starts at once.

## Fabric: considered, out of scope (ADR 0004)

Fabric was considered for analytics over the audit trail: mirroring the free-tier Cosmos DB account
into OneLake, for SQL and Power BI over every match. On 2026-10-19 it was left out of the
hackathon's scope; it's the route the analytics would take as the project grows. Nothing in the
build depends on it.

What exists from the first look: the member user `hudhud@…` with the **Fabric Administrator** role
(Fabric doesn't accept a personal Microsoft account, so a trial needs a member user of the tenant),
and a 60-day Fabric trial started 2026-10-18, which lapses by itself at no cost. The user has no
role on any Azure resource.

If the route is taken: sign in at app.fabric.microsoft.com as that user (two-step sign-in on), a
capacity in **Central India** (where the Cosmos DB account is: mirroring across regions pays
egress), a workspace, a mirrored Azure Cosmos DB database signing in as that user, and a
data-reader role for it on `hudhud-audit`. The owner does these steps; nobody else ever handles
that user's password. A paid F2 capacity (UAE North: $0.44 an
hour, about $321 a month running) is out of reach on the credit.

## The CLI: `scripts/az`, never the bare `az`

This machine's `az` on PATH is the Windows install (2.63.0). It is signed in to a **different
account and subscription** (a sponsorship that isn't this project's). Using it would risk creating
resources on the wrong bill, and logging in would change its default for every other tool.
The project's own login also sees the Pay-As-You-Go subscription, so the subscription is always
set explicitly.

So the project uses a Linux Azure CLI (installed with `pipx install azure-cli`) with its own config
folder, `~/.azure-hudhud`, through `scripts/az`. The Windows login is never read or changed.

```sh
scripts/az login --tenant <tenant from azure.local.md> --use-device-code   # the Monarch signs in
scripts/az account set --subscription <id from azure.local.md>
scripts/az account show -o table                                          # check before any create
```
