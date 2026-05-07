# ARCHITECTURE.md — InnerCircle AGI

> Production-grade multi-agent AI advisory system demonstrating 7 core software engineering concepts.

---

## 1. Clean Architecture

The codebase enforces strict **layer separation** — no layer depends on an outer layer.

```
┌─────────────────────────────────────────────────────────┐
│  API Layer       app/api/          (HTTP, routing)       │
├─────────────────────────────────────────────────────────┤
│  Agent Layer     app/agents/       (AI agent logic)      │
├─────────────────────────────────────────────────────────┤
│  Core Layer      app/core/         (config, security,    │
│                                    logging, middleware)  │
├─────────────────────────────────────────────────────────┤
│  Domain Layer    app/domain/       (models, schemas)     │
├─────────────────────────────────────────────────────────┤
│  Infrastructure  app/infrastructure/ (DB, AI client)     │
└─────────────────────────────────────────────────────────┘
```

| File | Responsibility |
|------|---------------|
| `app/domain/models.py` | SQLAlchemy ORM models (User, Session, Message, Insight) |
| `app/domain/schemas.py` | Pydantic v2 request/response schemas |
| `app/infrastructure/database.py` | DB engine & sessions |
| `app/infrastructure/openai_client.py` | OpenAI GPT-4o-mini API client |
| `app/infrastructure/chroma_client.py` | ChromaDB vector memory |
| `app/agents/base_agent.py` | Template Method — abstract agent base |
| `app/agents/council.py` | LangGraph router + agent registry |
| `app/agents/life_coach.py` | Life Coach agent |
| `app/agents/investment.py` | Investment & Finance agent |
| `app/agents/performance.py` | Performance Coach agent |
| `app/agents/career.py` | Career Strategist agent |
| `app/agents/health.py` | Health & Mind agent |
| `app/agents/synthesizer.py` | Cross-domain Synthesizer agent |
| `app/api/auth.py` | Auth endpoints (`/auth/*`) |
| `app/api/council.py` | Council endpoints (`/council/*`) |
| `app/api/profile.py` | Profile endpoints (`/profile/*`) |
| `app/api/insights.py` | Insights endpoints (`/insights/*`) |
| `app/api/deps.py` | FastAPI dependency injection |
| `app/core/config.py` | Pydantic Settings (type-safe env vars) |
| `app/core/security.py` | JWT & bcrypt utilities |
| `app/core/middleware.py` | Security headers + request logging |
| `app/core/metrics.py` | Custom Prometheus counters & gauges |
| `app/core/limiter.py` | Rate limiting setup |
| `app/tasks/insight_generator.py` | Celery background insight generation |

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
| `GET`  | `/council/agents` | ✅ | List all 6 council agents |
| `POST` | `/council/ask` | ✅ | Ask the council (full response) |
| `POST` | `/council/ask/stream` | ✅ | Ask the council (SSE streaming) |
| `GET`  | `/council/sessions` | ✅ | List conversation sessions |
| `GET`  | `/council/sessions/{id}` | ✅ | Get session with messages |
| `DELETE` | `/council/sessions/{id}` | ✅ | Delete a session |
| `POST` | `/profile/` | ✅ | Create user profile |
| `GET`  | `/profile/` | ✅ | Get user profile |
| `PUT`  | `/profile/` | ✅ | Update user profile |
| `GET`  | `/insights/` | ✅ | List proactive insights |
| `POST` | `/insights/{id}/read` | ✅ | Mark insight as read |
| `GET`  | `/health` | ❌ | Component health check |
| `GET`  | `/metrics` | ❌ | Prometheus metrics |

**Design principles applied:**
- ✅ Proper HTTP verbs (GET/POST/PUT/DELETE)
- ✅ HTTP status codes (200, 201, 204, 401, 404, 422, 503)
- ✅ Resource-based URL naming (nouns, not verbs)
- ✅ Pydantic v2 input validation with descriptive errors
- ✅ OpenAPI documentation with summaries and descriptions
- ✅ SSE streaming for real-time responses

---

## 3. Containerization

**Dockerfile** (multi-stage, `python:3.12-slim` base):

```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production image
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
COPY --chown=appuser:appgroup . .
USER appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose** (`docker-compose.yml`) services:

| Service | Image | Purpose |
|---------|-------|---------| 
| `app` | Custom build | FastAPI application |
| `db` | `postgres:16-alpine` | Primary database |
| `redis` | `redis:7-alpine` | Celery broker + cache |
| `celery_worker` | Custom build | Background insight generation |
| `celery_beat` | Custom build | Periodic task scheduler |
| `prometheus` | `prom/prometheus` | Metrics collection (optional) |
| `grafana` | `grafana/grafana` | Dashboards (optional) |

---

## 4. CI/CD Pipeline

**`.github/workflows/ci.yml`** — 3 sequential stages:

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
│   TEST      │  → 34 tests, PostgreSQL + Redis services
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Stage 3    │  🐳 docker build (multi-stage)
│   BUILD     │  → Validates Dockerfile compiles
└─────────────┘
```

---

## 5. Observability

### Logging (`app/core/logging.py`)
Structured formatter: `timestamp | level | module | message`

### Request Logging (`app/core/middleware.py` → `RequestLoggingMiddleware`)
Every request logs: method, path, status code, duration_ms, client_ip

### Prometheus Metrics (`/metrics`)

| Metric | Type | Description |
|--------|------|-------------|
| `innercircle_council_queries_total` | Counter | Total council queries |
| `innercircle_agent_queries_total` | Counter | Queries per agent role |
| `innercircle_llm_response_seconds` | Histogram | LLM response latency |
| `innercircle_insights_generated_total` | Counter | Proactive insights generated |
| `innercircle_auth_registrations_total` | Counter | User registrations |
| `innercircle_auth_failures_total` | Counter | Auth failures (by reason) |
| `innercircle_registered_users_total` | Gauge | Total registered users |
| `http_request_duration_seconds` | Histogram | Auto (FastAPI instrumentator) |

### Health Check (`/health`)
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-05-07T19:00:00+00:00",
  "components": {
    "api":            "ok",
    "database":       "ok",
    "llm":            "ok",
    "llm_model":      "gpt-4o-mini"
  }
}
```

---

## 6. Security

### Authentication & Authorization
- **JWT (HS256)** via `python-jose` — 24h expiry
- **bcrypt** password hashing via `passlib`
- Every council/profile/insights endpoint requires `Authorization: Bearer <token>`
- Sessions and messages are **user-scoped** — users cannot access each other's data

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
- Message: max 4000 chars, non-empty

---

## 7. AI Integration — Multi-Agent System

### Architecture

```
User Message
     ↓
[LangGraph Router] → keyword scoring → agent selection
     ↓
[Selected Agent] → ChromaDB memory → OpenAI GPT → store memory
     ↓
AgentResponse (content, role, model, tokens)
```

### Agents

| Agent | Role | Expertise |
|-------|------|-----------|
| 🧭 Yaşam Koçu | `life_coach` | CBT, Stoic philosophy, habit architecture |
| 📈 Yatırım & Finans | `investment` | Portfolio theory, macro analysis |
| ⚡ Performans Koçu | `performance` | Periodization, HRV, recovery |
| 🚀 Kariyer Stratejisti | `career` | Career capital, personal brand |
| 🧬 Sağlık Mimarı | `health` | Longevity, hormonal optimization |
| 🔮 Sentezci | `synthesizer` | Cross-domain synthesis |

### Design Patterns Used
See [docs/DESIGN_PATTERNS.md](docs/DESIGN_PATTERNS.md) for detailed documentation:
- **Singleton** — Single LLM client, config, ChromaDB
- **Template Method** — BaseAgent → 6 concrete agents
- **Strategy** — Routing algorithm selection
- **Observer** — SSE streaming, Celery insights
- **Registry/Factory** — Agent registry dictionary
- **MVC** — Domain/API/Static layer separation

---

## Quick Start

```bash
# 1. Clone & configure
git clone https://github.com/yahyaKocaman/InnerCircle-AGI
cd InnerCircle-AGI
cp .env.example .env

# 2. Set your OpenAI API key in .env
# OPENAI_API_KEY=sk-your-key-here

# 3. Docker
docker compose up -d --build

# 4. Run tests
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app
```

**Endpoints:**
- 🌐 App: http://localhost:8000
- 📖 Docs: http://localhost:8000/api/docs
- 📊 Metrics: http://localhost:8000/metrics
- 💚 Health: http://localhost:8000/health
