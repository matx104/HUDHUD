# Scripts

Everything that touches Azure signs in through `scripts/az`: the project's own Linux CLI with its own
config folder, never the machine's default `az` (docs/azure.md). The Python scripts share that
sign-in through `_azure.py`. "Read-only" means a script changes nothing in Azure.

## Every day

| Command | What it does | Azure | Cost |
|---|---|---|---|
| `make doctor` (`scripts/doctor.py`) | Checks the whole setup top to bottom: the sign-in and subscription, every resource and its guardrails (keys off, free tier, caps), the studio's identity, health and image, the budget, the showcase site, CI. Exits 1 on any failure | read-only | free |
| `make costs` (`scripts/costs.py`) | Month-to-date cost of `rg-hudhud` by service, and the $100 budget. Cost Management runs up to a day behind | read-only | free |
| `make smoke` (`scripts/smoke.py`) | Streams one short match from the live studio and checks every part: health, config, clock, cues with receipts, full time. `--models` narrates with Foundry | read-only (writes audit records) | free; `--models` under a cent |
| `make links` (`scripts/check_links.py`) | Checks every link on the showcase site and in the README | none | free |
| `.venv/bin/python scripts/audit.py runs` / `show RUN` | Browses the audit trail: recent runs with what aired and was refused, or one run's every record (`--out run.json` exports it) | read-only | free |

## Running and shipping

| Command | What it does | Azure | Cost |
|---|---|---|---|
| `scripts/live run --seed 21 --narrator foundry --audit cosmos` | One match in the console, narrated on Foundry, kept in the audit trail, traced | calls models | about $0.002 a match |
| `scripts/live narrator-eval --seeds 5` | The models compete for the job under ADR 0005's rule | calls models | a few cents |
| `make studio` (`scripts/studio`) | The studio on this machine, at http://localhost:8080 | calls models | per match, as above |
| `scripts/deploy-studio` | Builds the studio image, pushes it, rolls the container app onto it, tagged with the commit (refuses a dirty tree) | **changes the app** | registry storage |
| `scripts/studio-power on\|off\|status` | Keeps the live studio warm (one replica), lets it sleep when idle, or shows which. Keep it **on** from Oct 26 through Nov 10 | **changes the app** | on: about $5 a month |
| `make control-room` (`scripts/control_room.py`) | Deploys the HUDHUD workbook and writes the local control room's portal links (git-ignored) | **updates the workbook** | free |
| `make site-data` (`scripts/site_sample.py`) | Regenerates the showcase site's sample claim and match from a real offline run | none | free |

## Plumbing

| File | Role |
|---|---|
| `az` | The project's Azure CLI: run it exactly like `az` |
| `live-env` | Sourced by `live` and `studio`: the CLI first on PATH, the tenant pinned, the endpoints |
| `azure-mcp` | Starts the Azure MCP Server for GitHub Copilot agent mode (`.vscode/mcp.json`), signed in as the project CLI |
| `_azure.py` | Shared by the Python scripts: `az()`, the resource names, the studio's address |
