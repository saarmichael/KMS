# Task runner for the whole repo. `make <target>`; see PLAN.md "How we work".
.PHONY: db db-stop migrate dev api ui test test-live lint build deploy seed matrix logs

BACKEND = cd backend && uv run
FRONTEND = cd frontend && npm

db:            ## start Postgres (pgvector) and wait until it accepts connections
	docker compose up -d db
	@until docker compose exec -T db pg_isready -U kms -d kms >/dev/null 2>&1; do sleep 1; done

db-stop:
	docker compose stop db

migrate: db    ## apply migrations to the dev database
	$(BACKEND) alembic upgrade head

api: migrate   ## API with auto-reload on :8000
	$(BACKEND) uvicorn kms.main:app --reload --port 8000

ui:            ## Vite dev server on :5173 (proxies /api to :8000)
	$(FRONTEND) run dev

dev: migrate   ## API + UI together, fake adapters unless .env says otherwise
	@trap 'kill 0' INT TERM; \
	($(BACKEND) uvicorn kms.main:app --reload --port 8000) & \
	($(FRONTEND) run dev) & \
	wait

test: db       ## unit + integration tests (fake adapters, kms_test database)
	$(BACKEND) pytest -q --ignore=tests/live

test-live: db  ## adds the live vendor tests; needs GEMINI_API_KEY and VOYAGE_API_KEY
	$(BACKEND) pytest -q -m live tests/live

lint:
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .
	$(FRONTEND) run lint

build:         ## SPA build into the backend, then the container image
	$(FRONTEND) run build
	docker build -t kms .

deploy:        ## push the local directory to Railway
	railway up

seed:          ## uv run kms seed: ingest seed/<collection>/ through the upload service function (Phase 6)
	@echo "not yet: Phase 6"

matrix:        ## uv run kms matrix: run seed/demo/matrix.json against the API (Phase 6)
	@echo "not yet: Phase 6"

logs:
	railway logs
