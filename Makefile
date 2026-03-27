# ═══════════════════════════════════════════════════════════
#  InnerCircle AGI — Makefile
#  Usage: make <target>
# ═══════════════════════════════════════════════════════════

.PHONY: help up down restart logs shell test lint pull-model build clean ps

# ── Colors ───────────────────────────────────────────────────
GREEN  := \033[0;32m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
RESET  := \033[0m

help: ## Show this help message
	@echo ""
	@echo "  $(CYAN)InnerCircle AGI — Available Commands$(RESET)"
	@echo "  ──────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Docker ───────────────────────────────────────────────────

up: ## Start all services (detached)
	docker compose up -d --build
	@echo "$(GREEN)✓ InnerCircle AGI running at http://localhost:8000$(RESET)"
	@echo "$(YELLOW)  API docs: http://localhost:8000/api/docs$(RESET)"
	@echo "$(YELLOW)  Metrics:  http://localhost:8000/metrics$(RESET)"

up-monitoring: ## Start all services + Prometheus + Grafana
	docker compose --profile monitoring up -d --build
	@echo "$(GREEN)✓ Monitoring stack started$(RESET)"
	@echo "$(YELLOW)  Prometheus: http://localhost:9090$(RESET)"
	@echo "$(YELLOW)  Grafana:    http://localhost:3000  (admin/innercircle)$(RESET)"

down: ## Stop all services
	docker compose --profile monitoring down

restart: ## Restart the API service
	docker compose restart app

build: ## Build Docker images without starting
	docker compose build --no-cache

logs: ## Tail logs for all services
	docker compose logs -f --tail=100

logs-app: ## Tail API logs only
	docker compose logs -f app --tail=200

logs-celery: ## Tail Celery worker logs
	docker compose logs -f celery_worker celery_beat --tail=100

ps: ## Show service status
	docker compose ps

# ── Development ──────────────────────────────────────────────

shell: ## Open a shell inside the API container
	docker compose exec app bash

db-shell: ## Open PostgreSQL shell
	docker compose exec db psql -U postgres -d innercircle

redis-cli: ## Open Redis CLI
	docker compose exec redis redis-cli

# ── Ollama ───────────────────────────────────────────────────

pull-model: ## Pull DeepSeek-R1:8b model (run before `make up`)
	@echo "$(CYAN)Pulling deepseek-r1:8b — this may take a few minutes...$(RESET)"
	ollama pull deepseek-r1:8b
	@echo "$(GREEN)✓ Model ready$(RESET)"

ollama-status: ## Check Ollama connectivity and model availability
	@curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || \
		echo "$(YELLOW)API not running — start with: make up$(RESET)"

# ── Code Quality ─────────────────────────────────────────────

lint: ## Run ruff linter
	docker compose exec app ruff check .

format: ## Run ruff formatter
	docker compose exec app ruff format .

test: ## Run pytest tests
	docker compose exec app pytest tests/ -v --tb=short

# ── Data ─────────────────────────────────────────────────────

clean-volumes: ## Remove all Docker volumes (WARNING: deletes data!)
	@echo "$(YELLOW)WARNING: This will delete all database and vector memory data!$(RESET)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	docker compose down -v
	@echo "$(GREEN)✓ Volumes cleaned$(RESET)"

clean: ## Remove containers and images
	docker compose down --rmi local
