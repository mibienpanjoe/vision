.PHONY: setup services migrate api worker dispatch web dev stop browsers lint unit contracts web-check docs check integration browser-session reconcile-sources
setup:
	python3 scripts/local.py setup
services:
	docker compose up -d --wait db redis
migrate:
	python3 scripts/local.py migrate
api:
	python3 scripts/local.py api
worker:
	python3 scripts/local.py worker
dispatch:
	python3 scripts/local.py dispatch
web:
	pnpm --dir apps/web dev
dev: services migrate
	python3 scripts/local.py dev
stop:
	docker compose stop
browsers:
	pnpm --dir apps/web exec playwright install chromium
lint:
	uv run --project apps/api --locked ruff check apps/api/app apps/api/migrations apps/api/tests scripts
unit:
	uv run --project apps/api --locked pytest apps/api/tests -m 'not integration' -q
contracts:
	pnpm --dir packages/contracts generate
	git diff --exit-code -- packages/contracts/schema.json packages/contracts/index.ts
	pnpm --dir packages/contracts test
	pnpm --dir packages/contracts typecheck
web-check:
	pnpm --dir apps/web test:spans
	pnpm --dir apps/web build
	pnpm --dir apps/web typecheck
	pnpm --dir apps/web test tests/shell.spec.ts --workers=1
docs:
	python3 scripts/check_docs.py
check: lint unit contracts web-check docs
integration:
	python3 scripts/local.py integration
browser-session:
	uv run --project apps/api --locked python scripts/browser_session.py

reconcile-sources:
	python3 scripts/local.py reconcile-sources
