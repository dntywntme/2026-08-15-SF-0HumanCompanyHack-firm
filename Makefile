UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
RUN_ID ?= demo

# .env.example says "copy to .env", and for a long time nothing read the result:
# no dotenv dependency, no --env-file, so a reader filled it in, ran make run,
# and silently got the recorded tier with no explanation. Load it when it
# exists, and stay out of the way when it does not -- CI passes real environment
# variables and has no .env to find.
ENV_FILE := $(wildcard .env)
UVRUN = $(UV) run $(if $(ENV_FILE),--env-file .env,)

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
	$(UVRUN) pytest

lint: check-uv
	$(UVRUN) ruff check .
	$(UVRUN) ruff format --check .

fmt:
	$(UVRUN) ruff format .
	$(UVRUN) ruff check --fix .

run:
	$(UVRUN) company --run-id $(RUN_ID)

replay:
	$(UVRUN) company --replay $(RUN_ID)

e2e:
	cd tools/uitest && npm install --silent && node e2e.js

clean:
	rm -rf runs .pytest_cache .ruff_cache
