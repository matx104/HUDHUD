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
| `.venv/bin/python scripts/doctor.py --publish` | Runs the doctor and writes its checklist to `site/data/doctor.js`, the public proof on the site's Control room page (email addresses replaced) | read-only | free |
| `.venv/bin/python scripts/redact.py` | Covers every identifier in the Azure screenshots saved to `proof/raw/` (git-ignored) with solid boxes, by OCR plus optional manual boxes, and publishes them to the Control room page. **Look at every output before committing** | none | free |
| `.venv/bin/python scripts/drive_kit.py` | Builds the public media kit (the Read me and brand sheet PDFs from `kit/`, the crest and icons, the video's thumbnail, the approved screenshots, the sample recap as a page and a PDF) and syncs it to the Google Drive folder with rclone, shared as "anyone with the link can view". `--build` builds only; `--video demo.mp4` uploads the recording. Copies, never deletes. Needs Playwright (`pip install playwright`) and Chromium | none | free |
| `make realism` | Sets the generator's scorelines (seeds 0-199) against real international results since 2010 and writes `docs/realism.md` and `site/data/realism.js`. The real results (CC0, Mart Jürisoo) are downloaded to the git-ignored `benchmarks/` and never committed; the script prints the download line if they're missing | none | free |
| `scripts/edge` | Builds and deploys the Cloudflare Worker in front of the studio (`edge/`) with the cf CLI. Needs a Node with TypeScript support (an official Node 24 build) | Cloudflare | free |
| `.venv/bin/python scripts/social_card.py` | Prints the link-preview card (`site/assets/og.png`) from `kit/social-card.html`, with the site's address from `site/config.js`. Rerun when the address changes; `--out` to look first | none | free |
| `.venv/bin/python scripts/audit.py runs` / `show RUN` | Browses the audit trail: recent runs with what aired and was refused, or one run's every record (`--out run.json` exports it) | read-only | free |

## Running and shipping

| Command | What it does | Azure | Cost |
|---|---|---|---|
| `scripts/live run --seed 21 --narrator foundry --audit cosmos` | One match in the console, narrated on Foundry, kept in the audit trail, traced | calls models | about $0.002 a match |
| `scripts/live narrator-eval --seeds 5` | The models compete for the job under ADR 0005's rule | calls models | a few cents |
| `make studio` (`scripts/studio`) | The studio on this machine, at http://localhost:8091 | calls models | per match, as above |
| `scripts/deploy-studio` | Builds the studio image, pushes it, rolls the container app onto it, tagged with the commit (refuses a dirty tree) | **changes the app** | registry storage |
| `scripts/studio-power on\|off\|status` | Keeps the live studio warm (one replica), lets it sleep when idle, or shows which. Keep it **on** from Oct 26 through Nov 10 | **changes the app** | on: about $5 a month |
| `make control-room` (`scripts/control_room.py`) | Deploys the HUDHUD workbook and writes the portal links to `site/data/ops.js`, the owner's shortcuts on the site's Control room page (IDs only; the email-based directory name is never used) | **updates the workbook** | free |
| `make site-data` (`scripts/site_sample.py`) | Regenerates the showcase site's sample claim and match from a real offline run | none | free |
| `scripts/director.py` | Drives the demo video on one clock (docs/video.md): the owner's own Chrome on Windows, over the DevTools Protocol once they allow it, plays each take in a full-screen window, opens each tab ahead of its cut, clicks on the beats, and starts and stops OBS over obs-websocket. `--control FILE` keeps one connection for many takes; `--frames DIR` saves each shot; `--headless` tests the shots in a local Chromium | starts and stops an OBS recording | about two cents of models a take |
| `scripts/video_post.py` | Finishes the director's take: the voiceover read by Azure AI Speech and placed sentence by sentence on its shots, the captions burned in under each shot's title, the frames Chrome hadn't drawn yet held on the one before, the take's own sound ducked under the narration. `--plan` prints the timings; `--swap AT=FILE` lays a shot recorded alone over the take | writes `dist/video/` | about a cent of speech |
| `scripts/site_demo.py` | Records one match from the live studio (its stream, its ledger, ten questions with their answers and proofs) and copies the studio's pages into `site/demo/` with a replay shim, for the site's live demos. `--copy-only` refreshes the pages alone | read-only (writes audit records) | a few cents of models |

## Plumbing

| File | Role |
|---|---|
| `az` | The project's Azure CLI: run it exactly like `az` |
| `live-env` | Sourced by `live` and `studio`: the CLI first on PATH, the tenant pinned, the endpoints |
| `azure-mcp` | Starts the Azure MCP Server for GitHub Copilot agent mode (`.vscode/mcp.json`), signed in as the project CLI |
| `_azure.py` | Shared by the Python scripts: `az()`, the resource names, the studio's address |
