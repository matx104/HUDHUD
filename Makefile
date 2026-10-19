PY ?= python3.13
BIN := .venv/bin

.PHONY: setup test lint fmt schema demo eval site-data control-room doctor costs smoke links studio studio-offline edge realism site

setup:  ## create .venv and install both workspace packages (editable)
	$(PY) -m venv .venv
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements-dev.txt

test:
	$(BIN)/pytest
	node --test tests/site/*.test.cjs

lint:
	$(BIN)/ruff check . && $(BIN)/ruff format --check .

fmt:
	$(BIN)/ruff format . && $(BIN)/ruff check --fix .

schema:  ## regenerate the committed JSON Schema after editing models.py
	$(BIN)/python -m match_events schema

demo:  ## one synthetic match, end to end, in the console
	$(BIN)/python -m court run --seed 7

eval:  ## score the Scout's momentum calls against hidden ground truth (unseen seeds 60-99)
	$(BIN)/python -m court eval

realism:  ## the generator's scorelines against real international results (needs benchmarks/, see the script)
	$(BIN)/python scripts/realism.py

site-data:  ## regenerate the showcase data: the hero claim (chain.js) and the match (match.js)
	$(BIN)/python scripts/site_sample.py

control-room:  ## deploy the HUDHUD workbook and write the local control-room links (Azure)
	$(BIN)/python scripts/control_room.py

doctor:  ## check the whole setup: Azure guardrails, the studio, the site, CI (read-only)
	$(BIN)/python scripts/doctor.py

costs:  ## month-to-date cost by service and the $100 budget (read-only)
	$(BIN)/python scripts/costs.py

smoke:  ## stream one match from the live studio and check every part (free)
	$(BIN)/python scripts/smoke.py

links:  ## check every link on the showcase site and in the README
	$(BIN)/python scripts/check_links.py

studio:  ## the live studio at http://localhost:8091 (Foundry models, audit and traces on)
	scripts/studio

studio-offline:  ## the same studio with no Azure at all: the offline narrator, English (http://localhost:8091)
	$(BIN)/uvicorn court.server:app --host 127.0.0.1 --port 8091

edge:  ## deploy the Cloudflare Worker in front of the deployed studio (edge/, cf CLI)
	scripts/edge

site:  ## serve the showcase site at http://localhost:8000
	$(PY) -m http.server 8000 -d site
