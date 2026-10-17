# Azure: account, credits, guardrails

> Snapshot of the Azure for Students subscription as seen in the portal on 2026-10-18. Identifiers
> (subscription ID, tenant) live in the gitignored `azure.local.md`, because this repo goes public.

## The account

| | |
|---|---|
| Offer | Azure for Students (no card on file) |
| Credit | **$100**, $0.00 spent (October) |
| Credit expires | **2026-11-13** (26 days from 2026-10-18); "eligible students can renew" |
| 12-month free services | until 2027-10-18 |
| Role | Owner of the subscription |
| Status | Active, no resources yet |

**Dates that matter:**
- **Submission:** Oct 27, 11:59 PM PT, which is Oct 28, 11:59 AM PKT. The plan submits on the evening of Oct 27, PKT.
- **Judging:** the hackathon runs until Nov 21, but the credit expires on Nov 13. Anything live for the judges after Nov 13 needs the renewal, or the demo has to work without Azure (the offline backends already do).

## Free services that fit this build (from the portal's usage page)

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
2. **A budget on day one:** $100, with alerts at 25%, 50%, 75% and 90% to the account email.
3. **Model spend is the risk** (goals.md: the $100 is the ceiling, not the budget). A cheap model
   for detection summaries and a stronger one only for narrative. Demo matches are capped in
   length, responses are cached, and token cost is metered from the first call.
4. **No resource without a named reason** tied to the rubric (super-prompt.md).

## The CLI: `scripts/az`, never the bare `az`

This machine's `az` on PATH is the Windows install (2.63.0). It is signed in to a **different
account and subscription** (a sponsorship that isn't this project's). Using it would risk creating
resources on the wrong bill, and logging in would change its default for every other tool.

So the project uses a Linux Azure CLI (installed with `pipx install azure-cli`) with its own config
folder, `~/.azure-hudhud`, through `scripts/az`. The Windows login is never read or changed.

```sh
scripts/az login --tenant <tenant from azure.local.md> --use-device-code   # the Monarch signs in
scripts/az account set --subscription <id from azure.local.md>
scripts/az account show -o table                                          # check before any create
```
