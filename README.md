# InnerCircle AGI

> **"Tek bir AI değil. Senin adına düşünen, her alanda uzman bir konsey."**

InnerCircle AGI, kullanıcının hayatının gizli, profesyonel danışma kuruludur. Altı uzman ajan aynı anda çalışarak derin, veri odaklı ve sofistike öneriler sunar — ama asla karar vermez, dayatmaz.

---

## Konsey Üyeleri

| Ajan | Alan | Uzmanlık |
|------|------|----------|
| 🧭 Yaşam Koçu | Anlam & Büyüme | CBT, Stoa felsefesi, alışkanlık mimarisi |
| 📈 Yatırım & Finans | Servet | Portföy teorisi, makroekonomi, risk analizi |
| ⚡ Performans Koçu | Fiziksel | Periodizasyon, HRV, recovery bilimi |
| 🚀 Kariyer Stratejisti | Profesyonel | Kariyer kapitali, müzakere, güç dinamikleri |
| 🧬 Sağlık & Zihin Mimarı | Biyolojik | Longevity, hormonal optimizasyon, nörobilim |
| 🔮 Sentezci | Sistemik | Çapraz alan bağlantıları, kaldıraç analizi |

---

## Mimari

```
┌──────────────────────────────────────────────────────────────┐
│                    InnerCircle AGI                           │
├──────────────┬───────────────────────────────────────────────┤
│  Frontend    │  FastAPI App (Docker)                         │
│  HTML/CSS/JS │                                               │
│  • CoT Panel │  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  • SSE Stream│  │ LangGraph│  │ChromaDB  │  │Prometheus │  │
│  • Auth SPA  │  │ Router   │  │Vector DB │  │ Metrics   │  │
└──────────────┴──┤          ├──┤          ├──┤           ├──┘
                  └────┬─────┘  └──────────┘  └───────────┘
                       │
              ┌────────┼────────┐
              │        │        │
          Life Coach  Career  Health  ...
              │
         ┌────┴────┐
         │ Ollama  │ deepseek-r1:8b
         └─────────┘
              │
     ┌────────┴────────┐
     │   Celery/Redis  │
     │ Background Jobs │
     └─────────────────┘
```

### Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| **Web Framework** | FastAPI + uvicorn |
| **AI Model** | DeepSeek-R1:8b via Ollama (ücretsiz, local) |
| **Agent Orchestration** | LangGraph multi-agent swarm |
| **Vector Memory** | ChromaDB (per-agent collections) |
| **Persistence** | PostgreSQL 16 |
| **Background Tasks** | Celery + Redis |
| **Observability** | Prometheus + Grafana |
| **Auth** | JWT (HS256) + bcrypt |
| **CI/CD** | GitHub Actions + GHCR |
| **Containerization** | Docker + Docker Compose |

---

## Hızlı Başlangıç

### Ön Koşullar

- Docker & Docker Compose
- [Ollama](https://ollama.ai) (host makinede)

### 1. Modeli İndir

```bash
ollama pull deepseek-r1:8b
ollama serve
```

### 2. Projeyi Başlat

```bash
# Repoyu klonla
git clone https://github.com/yahyaKocaman/smart-task-ai
cd smart-task-ai

# .env dosyası oluştur
cp .env.example .env
# SECRET_KEY'i değiştir!

# Servisleri başlat
make up
# veya: docker compose up -d --build
```

### 3. Kullan

| URL | Açıklama |
|-----|---------|
| http://localhost:8000 | Ana uygulama (SPA) |
| http://localhost:8000/api/docs | OpenAPI dokümantasyonu |
| http://localhost:8000/metrics | Prometheus metrikleri |
| http://localhost:8000/health | Sağlık kontrolü |

---

## Make Komutları

```bash
make up              # Tüm servisleri başlat
make up-monitoring   # + Prometheus & Grafana
make down            # Durdur
make logs            # Logları takip et
make logs-app        # Sadece API logları
make shell           # Container içine gir
make pull-model      # deepseek-r1:8b indir
make test            # Testleri çalıştır
make lint            # Kod kalite kontrolü
```

---

## Monitoring (İsteğe Bağlı)

```bash
make up-monitoring
```

| Servis | URL | Credentials |
|--------|-----|-------------|
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / innercircle |

---

## DeepSeek-R1 Chain-of-Thought UX

Bu projede DeepSeek-R1 modeli kullanılır. Model yanıt vermeden önce `<think>...</think>` blokları içinde iç monolog üretir.

Frontend bu bloğu **"Analiz ediliyor…"** paneli olarak gösterir:
- Panel otomatik açılır ve reasoning içeriğini gösterir
- 2 saniye sonra otomatik collapse olur
- Kullanıcı isterse manuel açabilir/kapatabilir
- Ham `<think>` tagları hiçbir zaman kullanıcıya gösterilmez

---

## API Referansı

### Konsey'e Sor
```bash
POST /council/ask
Authorization: Bearer <token>

{
  "message": "Kariyer geçişi hakkında ne düşünüyorsun?",
  "agent_role": "career",    # null ise otomatik yönlendirme
  "session_id": null         # null ise yeni oturum
}
```

### Streaming (SSE)
```bash
POST /council/ask/stream
# Server-Sent Events formatında token-by-token yanıt
# Özel eventler: __THINKING_START__, __THINKING_END__
```

---

## Proje Yapısı

```
smart-task-ai/
├── app/
│   ├── agents/           # 6 konsey ajanı + orchestrator
│   │   ├── base_agent.py # DeepSeek-R1 CoT aware base
│   │   ├── council.py    # LangGraph router
│   │   ├── life_coach.py
│   │   ├── investment.py
│   │   ├── performance.py
│   │   ├── career.py
│   │   ├── health.py
│   │   └── synthesizer.py
│   ├── api/              # REST endpoints
│   ├── core/             # Config, security, metrics
│   ├── domain/           # SQLAlchemy models + Pydantic schemas
│   ├── infrastructure/   # Ollama, ChromaDB, DB clients
│   ├── static/           # Frontend SPA
│   └── tasks/            # Celery background tasks
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── .github/workflows/    # CI (lint+test+build) + CD (GHCR push)
├── Dockerfile            # Multi-stage, non-root
├── docker-compose.yml    # + monitoring profile
└── Makefile
```

---

## CI/CD

| Pipeline | Tetikleyici | Adımlar |
|----------|-------------|---------|
| `ci.yml` | PR + main push | lint → test → docker build |
| `publish.yml` | main + tag (v*.*.*) | build → GHCR push (amd64+arm64) |

---

## Güvenlik

- JWT HS256 token authentication
- bcrypt şifre hashing
- Rate limiting (SlowAPI)
- OWASP HTTP security headers
- Non-root Docker user
- SECRET_KEY environment variable (asla hardcode değil)
