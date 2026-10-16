# pl-hackathon *(placeholder name — see project-names.md)*

> Microsoft × Premier League — **Inside the Game: Developer Hackathon** (Oct 2026)
> AI match intelligence on synthetic football-realistic data. **Solo build.**

**Status:** 🐣 Phase 1 skeleton: one synthetic match flows end to end through all five agents (offline backends), 48 tests green, CI on every push. Pending: name + domain, Azure activation, Foundry-hosted LLM backends.

## Quickstart

```sh
make setup   # python3.13 venv + both workspace packages, editable
make test    # pytest: generator realism, Critic checks, workflow loop, warm-path failure
make demo    # one synthetic match, all five agents, in the console
```

`python -m court run --help` lists the options (`--mode casual|analyst`, `--speed`, `--json` for the machine-readable cue stream, `--overreach` to make the offline narrator deliberately overreach so the Critic has something to reject).

## Layout

- `packages/event-schema/` (`match_events`): the stream contract (Pydantic + committed JSON Schema) and the deterministic synthetic match generator
- `apps/api/` (`court`): the agents. Orchestrator + Scout (hot path); Narrator → Critic → Localizer as an Agent Framework workflow (warm path)
- `docs/adr/`: architecture decisions (start with 0001, hot path / warm path)

## Files

- **super-prompt.md** — the Claude Code master brief: read-first order, locked architecture, hard constraints, session definitions of done
- **plan.md** — phased build plan (Oct 18 → 27) with definitions of done, cut order, and standing risks
- **task.md** — the official ask, decoded: rubric, prize categories, hard requirements, dates + the full Challenge brief
- **ideas.md** — solution options + the current fusion lean + decision gates
- **brand.md** — naming program, identity system, video compliance laws
- **project-names.md** — verified candidate register (all roots, live RDAP-checked 2026-10-16)
- **projects.md** — the reusable arsenal: existing projects → patterns → which idea they feed
- **inspiration.md** + **inspiration-projects.json** — the 150-project competitive field: lane census, threat tiers, differentiation memo
- **awards.md** — the six prize lanes: official per-member packages, FMV, sweep math
- **goals.md** — the Grand Slam doctrine: all-six declaration, award→feature build contract, public-intention language, kill criteria

## Build window

Oct 18–20 explore/architect · Oct 21–25 build · Oct 26 polish + 110s video · **Oct 27 submit** · winners Nov 20.

## Rules that bind

- Synthetic data only — no real PL match data
- Demo video < 2:00 hard cap · public URL
- Repo goes **public** at submission (private until showcase-ready)
- New code — patterns reused from existing projects, never the repos themselves
