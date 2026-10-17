PY ?= python3.13
BIN := .venv/bin

.PHONY: setup test lint fmt schema demo site-data site

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

site-data:  ## regenerate the showcase data: the hero claim (chain.js) and the match (match.js)
	$(BIN)/python scripts/site_sample.py

site:  ## serve the showcase site at http://localhost:8000
	$(PY) -m http.server 8000 -d site
