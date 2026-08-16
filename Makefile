# Day-to-day commands so nobody memorizes CLI args. `make help` lists them.

.PHONY: help setup serve front dev check test e2e test-all texmf docker-build docker-up

TEXMF_DIR := $(HOME)/.local/share/papercli/texmf

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## install backend + frontend deps, create .env from the sample if missing
	uv sync --extra server
	npm install
	test -f .env || cp .env.sample .env

serve: ## backend API on :8000 (loads .env)
	uv run --env-file .env --extra server papercli serve --reload

front: ## frontend dev server on :5173 (proxies /api)
	npm run dev

dev: ## backend + frontend together
	$(MAKE) -j2 serve front

check: ## pyright + ruff + svelte-check
	uv run --with pyright --extra server pyright papercli
	uvx ruff check papercli tests
	uvx ruff format --check papercli tests
	npm run check

test: ## unit tests + headless browser e2e (starts both servers itself)
	uv run pytest
	npx playwright test --project=e2e

e2e: ## browser e2e only
	npx playwright test --project=e2e

texmf: ## fetch LaTeX classes tectonic's bundle lacks (llncs); wire via PARITEX_SEARCH_PATHS in .env
	mkdir -p $(TEXMF_DIR)
	curl -fsSL -o /tmp/llncs.zip https://mirrors.ctan.org/macros/latex/contrib/llncs.zip
	unzip -jo /tmp/llncs.zip 'llncs/*.cls' 'llncs/*.bst' -d $(TEXMF_DIR)
	rm /tmp/llncs.zip
	@echo "add to .env: PARITEX_SEARCH_PATHS=$(TEXMF_DIR)"

docker-build: ## build the deployment image (frontend + API + tectonic + claude)
	docker compose build

docker-up: ## build and (re)start the container, serving on :5060 (all interfaces, gated by PAPERCLI_PASSWORD)
	docker compose up -d --build
