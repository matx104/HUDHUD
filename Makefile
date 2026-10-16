PY ?= python3.13
BIN := .venv/bin

.PHONY: setup test lint fmt schema demo

setup:  ## create .venv and install both workspace packages (editable)
	$(PY) -m venv .venv
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements-dev.txt

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check . && $(BIN)/ruff format --check .

fmt:
	$(BIN)/ruff format . && $(BIN)/ruff check --fix .

schema:  ## regenerate the committed JSON Schema after editing models.py
	$(BIN)/python -m match_events schema

demo:  ## one synthetic match, end to end, in the console
	$(BIN)/python -m court run --seed 7
