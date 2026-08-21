.DEFAULT_GOAL := help
SHELL := /bin/bash

PYTHON  ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
# Repo-local ruleset wins so `make lint` and CI agree.
MDCONFIG ?= $(shell [ -f .markdownlint-cli2.jsonc ] && echo .markdownlint-cli2.jsonc || echo $(HOME)/.markdownlint-cli2.jsonc)
LINT    := npx --yes markdownlint-cli2 --config $(MDCONFIG)
ARTICLES := articles/*.md
BASE     ?= origin/main

# Articles touched relative to $(BASE), which is what CI gates on.
CHANGED := $(shell git diff --name-only --diff-filter=d $(BASE)...HEAD -- 'articles/*.md' 2>/dev/null; \
                   git diff --name-only --diff-filter=d -- 'articles/*.md' 2>/dev/null; \
                   git ls-files --others --exclude-standard -- 'articles/*.md' 2>/dev/null)

.PHONY: help setup check validate validate-changed lint lint-changed links links-external index index-check diagrams schedule-dry clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv and install script dependencies
	python3 -m venv .venv
	.venv/bin/pip install --quiet --upgrade pip
	.venv/bin/pip install --quiet -r scripts/requirements.txt -r scripts/requirements-images.txt
	@echo "[+] .venv ready"

check: validate lint links ## Run every check CI runs, over the whole repo

validate: ## Validate frontmatter and asset references
	$(PYTHON) scripts/validate_articles.py --all

lint: ## markdownlint every article
	$(LINT) "$(ARTICLES)"

lint-changed: ## Fail only if changed articles ADD markdownlint errors (what CI gates on)
	$(PYTHON) scripts/lint_ratchet.py --base $(BASE) --changed

validate-changed: ## Validate only the articles changed vs $(BASE)
	@if [ -z "$(CHANGED)" ]; then echo "[-] No changed articles."; \
	else $(PYTHON) scripts/validate_articles.py $(sort $(CHANGED)); fi

links: ## Check dev.to cross-links and this repo's own asset URLs
	$(PYTHON) scripts/check_links.py --all

links-external: ## Also check third-party links (slow, reports link rot)
	$(PYTHON) scripts/check_links.py --all --external

index: ## Regenerate INDEX.md and the README stats block
	$(PYTHON) scripts/gen_index.py

index-check: ## Fail if INDEX.md or README stats are stale
	$(PYTHON) scripts/gen_index.py --check

diagrams: ## Re-render every D2 source to PNG
	@shopt -s nullglob; \
	count=0; \
	for src in articles/assets/*/diagrams/*.d2; do \
	  d2 --sketch --theme 200 --scale 3 "$$src" "$${src%.d2}.png" >/dev/null || exit 1; \
	  count=$$((count+1)); \
	done; \
	echo "[+] Rendered $$count diagram(s)"

schedule-dry: ## Show which articles the scheduler would publish (writes nothing)
	$(PYTHON) scripts/publish_scheduler.py --dry-run

clean: ## Remove generated Python caches
	find scripts -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
