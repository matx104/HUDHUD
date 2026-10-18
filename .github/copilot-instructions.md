# Working on HUDHUD with GitHub Copilot

HUDHUD is live football commentary in which every claim carries its evidence. A Scout detects
moments in a synthetic match, a Narrator writes the line, a Critic recomputes every number from raw
events and refuses what it can't verify, a Localizer translates, and an Orchestrator keeps the
broadcast going when an agent fails. Read `goals.md`, `plan.md` and `docs/adr/` before larger changes.

## The laws (never trade these for a passing test)

- **Code computes every number.** A claim carries its citations, the assertions the Critic
  recomputes, and its figures (every number the text may state). A model writes prose from facts
  it is given; it never chooses evidence or states a number code didn't compute.
- **The Critic fails closed.** A claim airs only if every check passes. Don't loosen a check, add
  an exception or skip a test to get a claim on air: fix the claim, the figures or the detector.
- **Synthetic data only.** Every club, player and match is invented by `packages/event-schema`.
  No real league, club, player or match data, and no third-party trademarks, in anything a viewer
  sees. Real datasets may be used only as benchmarks, credited, and never shown as product data.
- **The product name comes from config:** `court.config.product_name()` in Python and
  `site/config.js` on the site. Never hardcode it. Don't name the product or a feature with a
  word starting Match, Pitch or Touch.

## How to change things

- Tests first, and keep CI green: `make test` (pytest and the site's `node --test`) and
  `make lint` (Ruff) before every commit. `make eval` scores momentum calls on unseen seeds 60-99;
  `tests/test_evals.py` holds a precision floor.
- Small conventional commits on `main` (`feat(api): ...`, `docs: ...`).
- Match the surrounding code: comment density, naming and idiom. Docstrings say why, not what.
- Strings in Urdu or Arabic are marked `data-owner-review` on the site; the owner signs them off.
- Credit what you use: a dataset, library, font, talk or idea goes on the site's Credits page
  (`site/index.html`, `data-page="credits"`) with its author, link and license, in the same commit.

## Azure

- Use `scripts/az`, never the machine's default `az`: it is the project's own CLI and sign-in.
  The subscription is **Azure for Students**, with a $100 credit and its spending limit on. Never
  create anything in "Azure subscription 1": it is pay-as-you-go with no spending limit.
- Resources live in `rg-hudhud`: the Foundry models in UAE North (the only allowed region with
  model deployments), the Cosmos DB audit trail in Central India (UAE North refused new accounts).
- No keys. Microsoft Entra ID only; key-based auth stays disabled.
- `scripts/live run --seed 21 --narrator foundry --audit cosmos` narrates a match on the Foundry
  models and keeps every output in the audit trail (Cosmos DB, free tier, capped at 1,000 RU/s).
  It costs under a cent; don't loop it.
- The Azure MCP Server (`.vscode/mcp.json`, via `scripts/azure-mcp`) signs in as the same CLI.
  Ask before any call that creates, changes or deletes a resource.
- The Critic is an MCP server too (`hudhud-critic` in `.vscode/mcp.json`, ADR 0007): before stating a
  fact about a demo match, put the claim to `verify_claim` and back every number with an assertion
  from `match_stats`.

## The site

`site/index.html` is the whole site: one file, one `<section data-page>` per page, hash routes
(`#/how`). Keep it a single HTML file. Colors are the tokens at the top of `site/assets/site.css`.
Check pages at phone width, with reduced motion, and with keyboard focus visible.
