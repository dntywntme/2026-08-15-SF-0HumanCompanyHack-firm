UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
RUN_ID ?= demo

.PHONY: setup test lint fmt run replay e2e clean

setup:
	$(UV) sync

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

run:
	$(UV) run company --run-id $(RUN_ID)

replay:
	$(UV) run company --replay $(RUN_ID)

e2e:
	cd tools/uitest && npm install --silent && node e2e.js

clean:
	rm -rf runs .pytest_cache .ruff_cache
