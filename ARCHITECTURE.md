# ARCHITECTURE.md — Smart Task AI

> Production-grade microservice demonstrating 7 core software engineering concepts.

---

## 1. Clean Architecture

The codebase enforces strict **layer separation** — no layer depends on an outer layer.

```
┌─────────────────────────────────────────────────────────┐
│  API Layer       app/api/          (HTTP, routing)       │
├─────────────────────────────────────────────────────────┤
│  Core Layer      app/core/         (config, security,    │
│                                    logging, middleware)  │
├─────────────────────────────────────────────────────────┤
│  Domain Layer    app/domain/       (models, schemas)     │
├─────────────────────────────────────────────────────────┤
│  Infrastructure  app/infrastructure/ (DB, AI service)   │
└─────────────────────────────────────────────────────────┘
```

| File | Responsibility |
|------|---------------|
| `app/domain/models.py` | SQLAlchemy ORM models (pure data) |
| `app/domain/schemas.py` | Pydantic v2 request/response schemas |
| `app/infrastructure/database.py` | DB engine & sessions |
| `app/infrastructure/ai_service.py` | AI priority & category engine |
| `app/api/auth.py` | Auth endpoints (`/auth/*`) |
| `app/api/tasks.py` | Task CRUD endpoints (`/tasks/*`) |
| `app/api/deps.py` | FastAPI dependency injection |
| `app/core/config.py` | Pydantic Settings (type-safe env vars) |
| `app/core/security.py` | JWT & bcrypt utilities |
| `app/core/middleware.py` | Security headers + request logging |
| `app/core/metrics.py` | Custom Prometheus counters & gauges |
| `app/core/limiter.py` | Rate limiting setup |

---

## 2. REST API Design

**Framework:** FastAPI (OpenAPI 3.1, auto-generated Swagger UI)

**Interactive docs:** `http://localhost:8000/api/docs`

### Endpoint Map

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | ❌ | Create account (5 req/min) |
| `POST` | `/auth/login` | ❌ | Login, get JWT (10 req/min) |
| `GET`  | `/auth/me` | ✅ | Current user profile |
| `POST` | `/tasks/` | ✅ | Create task (AI priority) |
| `GET`  | `/tasks/` | ✅ | List tasks (filtered) |
| `GET`  | `/tasks/stats` | ✅ | Dashboard statistics |
| `GET`  | `/tasks/{id}` | ✅ | Get single task |
| `PUT`  | `/tasks/{id}` | ✅ | Update task |
| `POST` | `/tasks/{id}/complete` | ✅ | Mark complete |
| `DELETE` | `/tasks/{id}` | ✅ | Delete task |
| `GET`  | `/health` | ❌ | Component health check |
| `GET`  | `/metrics` | ❌ | Prometheus metrics |

**Design principles applied:**
- ✅ Proper HTTP verbs (GET/POST/PUT/DELETE)
- ✅ HTTP status codes (201 Created, 204 No Content, 401, 404, 422)
- ✅ Resource-based URL naming (nouns, not verbs)
- ✅ Pydantic v2 input validation with descriptive errors
- ✅ OpenAPI documentation with summaries and descriptions

---

## 3. Containerization

**Dockerfile** (`python:3.12-slim` base):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Docker Compose** (`docker-compose.yml`) services:

| Service | Image | Purpose |
|---------|-------|---------|
| `app` | Custom build | FastAPI application |
| `db` | `postgres:16-alpine` | Primary database |

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f app

# Stop
docker compose down
```

---

## 4. CI/CD Pipeline

**`.github/workflows/ci.yml`** — 4 sequential stages:

```
Push to GitHub
      │
      ▼
┌─────────────┐
│  Stage 1    │  🔍 Lint & Format (ruff)
│   LINT      │  → Fails fast on code quality issues
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Stage 2    │  🧪 pytest with coverage report
│   TEST      │  → 30+ tests, coverage uploaded to Codecov
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Stage 3    │  🐳 docker build + smoke test
│   BUILD     │  → curl /health must return 200
└──────┬──────┘
       │  (only on main branch)
       ▼
┌─────────────┐
│  Stage 4    │  📦 Push to GitHub Container Registry
│   PUBLISH   │  → ghcr.io/username/smart-task-ai:latest
└─────────────┘
```

---

## 5. Observability

### Logging (`app/core/logging.py`)
Structured formatter: `timestamp | level | module | message`

```
2026-03-26 21:00:00 | INFO     | app.api.auth  | User logged in: yahya
2026-03-26 21:00:01 | INFO     | app.core.middleware | request completed
```

### Request Logging (`app/core/middleware.py` → `RequestLoggingMiddleware`)
Every request logs: method, path, status code, duration_ms, client_ip

### Prometheus Metrics (`/metrics`)

| Metric | Type | Description |
|--------|------|-------------|
| `smarttask_tasks_created_total` | Counter | Tasks created (by priority) |
| `smarttask_tasks_completed_total` | Counter | Tasks completed |
| `smarttask_tasks_deleted_total` | Counter | Tasks deleted |
| `smarttask_auth_registrations_total` | Counter | Successful registrations |
| `smarttask_auth_logins_total` | Counter | Successful logins |
| `smarttask_auth_failures_total` | Counter | Auth failures (by reason) |
| `smarttask_ai_priority_predictions_total` | Counter | AI predictions (by result) |
| `smarttask_registered_users_total` | Gauge | Total registered users |
| `http_request_duration_seconds` | Histogram | Auto (FastAPI instrumentator) |

### Health Check (`/health`)
```json
{
  "status": "ok",
  "version": "2.0.0",
  "timestamp": "2026-03-26T21:00:00+00:00",
  "components": {
    "api":      "ok",
    "database": "ok"
  }
}
```

> **Grafana Dashboard:** Import Prometheus datasource → add panels for all metrics above

---

## 6. Security

### Authentication & Authorization
- **JWT (HS256)** via `python-jose` — 24h expiry
- **bcrypt** password hashing via `passlib`
- Every task endpoint requires `Authorization: Bearer <token>`
- Tasks are **user-scoped** — users cannot access each other's data

### Rate Limiting (`slowapi`)
```
POST /auth/register →  5 requests / minute / IP
POST /auth/login    → 10 requests / minute / IP
```

### Security Headers (`app/core/middleware.py`)
```
X-Content-Type-Options:    nosniff
X-Frame-Options:           DENY
X-XSS-Protection:          1; mode=block
Referrer-Policy:           strict-origin-when-cross-origin
Permissions-Policy:        geolocation=(), microphone=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### Input Validation
- Pydantic v2 validators on all request bodies
- Username: alphanumeric, min 3 chars
- Password: min 6 chars
- Email: RFC 5321 format validated

---

## 7. AI Integration

**Location:** `app/infrastructure/ai_service.py`

The AI service analyzes task title + description to:

1. **Predict priority** — Keyword-semantic matching across 50+ Turkish & English terms:

| Priority | Example Keywords |
|----------|-----------------|
| 🔴 CRITICAL | kritik, emergency, bugün bitmeli, asap |
| 🟠 HIGH | acil, urgent, deadline, yarına kadar |
| 🟡 MEDIUM | bu hafta, gerekli, should do |
| 🟢 LOW | zamanında, nice to have, boş vakitte |

2. **Suggest category** — Detects category from text:

| Category | Keywords |
|----------|---------|
| İş | toplantı, proje, rapor, meeting, client |
| Kişisel | alışveriş, aile, shopping, family |
| Sağlık | doktor, ilaç, hastane, doctor |
| Finans | fatura, banka, bill, payment |
| Eğitim | ders, ödev, okul, exam, study |

> **Future:** Replace with Ollama (local LLM) for semantic understanding — see EchoSelf AGI roadmap.

---

## Quick Start

```bash
# 1. Clone & configure
git clone https://github.com/yahyaKocaman/smart-task-ai
cd smart-task-ai
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
uvicorn main:app --reload --port 8000

# 4. Run tests
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app

# 5. Docker
docker compose up -d
```

**Endpoints:**
- 🌐 App: http://localhost:8000
- 📖 Docs: http://localhost:8000/api/docs
- 📊 Metrics: http://localhost:8000/metrics
- 💚 Health: http://localhost:8000/health
