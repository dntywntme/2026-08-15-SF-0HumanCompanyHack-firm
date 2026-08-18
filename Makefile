UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
RUN_ID ?= demo

.PHONY: check-uv setup test lint fmt run replay e2e clean

# `make setup` is the first command the README gives a new reader, and uv
# missing from PATH is the most likely thing to go wrong on a fresh machine.
# Without this it fails as "No such file or directory" against a path the reader
# never chose, which says nothing about what to do next.
check-uv:
	@command -v $(UV) >/dev/null 2>&1 || { \
	  echo "uv not found at '$(UV)'."; \
	  echo "  install it:   curl -LsSf https://astral.sh/uv/install.sh | sh"; \
	  echo "  or point at yours:  make <target> UV=/path/to/uv"; \
	  exit 1; }

setup: check-uv
	$(UV) sync

test: check-uv
	$(UV) run pytest

lint: check-uv
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
