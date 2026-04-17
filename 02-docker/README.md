# Section 2 — Docker: Dong Goi Agent Thanh Container

## Muc tieu hoc
- Hieu container la gi va tai sao can no
- Viet Dockerfile dung cach: single-stage vs multi-stage
- Dung Docker Compose de chay multi-service stack
- Demo mot multi-turn chatbot co session memory
- Chay duoc voi provider that qua OpenAI-compatible API
- Thiet ke san provider wrapper de doi giua OpenAI, OpenRouter, va custom provider

---

## Tinh nang chatbot cua section nay
- `POST /chat`: chat multi-turn, tu tao session moi neu chua co `session_id`
- `POST /sessions`: tao session truoc neu muon
- `GET /sessions/{session_id}`: xem lich su gan nhat
- `DELETE /sessions/{session_id}`: xoa session
- `GET /providers`: xem 3 provider wrapper va sample client config

Section nay ho tro 2 mode:
- **Live mode** neu provider co API key trong `.env.local`
- **Mock fallback** neu thieu key hoac bat `CHATBOT_MOCK_ONLY=true`

Giao dien demo co san tai:
- `http://localhost:8000/ui` cho basic image
- `http://localhost:8080/ui` cho production stack

### Provider wrapper co san
- `openai`
- `openrouter`
- `custom`

Custom provider preview:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("SHOPAIKEY_API_KEY"),
    base_url="https://api.shopaikey.com/v1",
    default_headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36"
    },
)
```

Model mac dinh cho custom provider:

```text
qwen3-coder-480b-a35b-instruct
```

---

## Vi du Basic — Dockerfile Don Gian

```
develop/
├── app.py
├── Dockerfile
├── .dockerignore
└── requirements.txt
```

### Chay basic image
```bash
# Root .env.local da duoc gitignore, dung de giu API key local
# Neu chua co, copy tu file mau:
# cp .env.example .env.local

# Build from project root
docker build -f 02-docker/develop/Dockerfile -t agent-develop .

# Run container
docker run --rm -p 8000:8000 \
  --env-file .env.local \
  agent-develop
```

### Test basic chatbot
```bash
# Health
curl http://localhost:8000/health

# Xem provider wrapper
curl http://localhost:8000/providers

# Mo giao dien browser
# http://localhost:8000/ui

# Turn 1: tao session moi va hoi cau dau tien
curl http://localhost:8000/chat -X POST \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","question":"Hello, introduce yourself in one sentence."}'
```

Lay `session_id` tu response roi dung lai:

```bash
# Turn 2: hoi tiep cung session
curl http://localhost:8000/chat -X POST \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","session_id":"<SESSION_ID>","question":"What did I ask before?"}'
```

Swagger UI:

```text
http://localhost:8000/docs
```

---

## Vi du Advanced — Multi-Stage + Docker Compose

```
production/
├── main.py
├── Dockerfile
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
└── requirements.txt
```

### Chay full stack
```bash
# Neu chua co, copy tu file mau:
# cp .env.example .env.local

# Build + start all services from project root
docker compose -f 02-docker/production/docker-compose.yml up --build
```

Services:
- `agent`: FastAPI chatbot
- `redis`: cache service
- `qdrant`: vector database service
- `nginx`: reverse proxy

### Test production stack
```bash
# Trang thai services
docker compose -f 02-docker/production/docker-compose.yml ps

# Health qua Nginx
curl http://localhost:8080/health

# Danh sach provider
curl http://localhost:8080/providers

# UI cho lecturer demo
# http://localhost:8080/ui

# Turn 1
curl http://localhost:8080/chat -X POST \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","question":"Explain Docker in one short paragraph."}'

# Turn 2
curl http://localhost:8080/chat -X POST \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","session_id":"<SESSION_ID>","question":"Summarize our earlier context."}'
```

Swagger UI:

```text
http://localhost:8080/docs
```

Dung stack:

```bash
docker compose -f 02-docker/production/docker-compose.yml down
```

---

## So sanh image size

```bash
docker images | grep agent
# agent-develop      python:3.11 base image
# agent-production   python:3.11-slim + multi-stage
```

Y nghia:
- Basic de hoc cau truc Dockerfile
- Advanced de hoc multi-stage build va Compose orchestration

---

## Tai sao multi-stage nho hon?

```dockerfile
# Stage 1: builder
FROM python:3.11-slim AS builder
RUN pip install --user -r requirements.txt

# Stage 2: runtime
FROM python:3.11-slim AS runtime
COPY --from=builder /root/.local /home/appuser/.local
```

Final image chi copy package can de chay, khong copy build tool va layer tam.

---

## Goi y demo voi giang vien

1. Mo `http://localhost:8080/ui` va chon provider `custom`.
2. Hoi mot cau dau tien de tao session moi.
3. Hoi tiep mot cau follow-up trong cung session de chung minh multi-turn.
4. Neu can, mo `GET /providers` de cho thay wrapper `openai`, `openrouter`, `custom`.
5. Mo `GET /sessions/{session_id}` de cho thay lich su hoi dap duoc giu trong memory.
6. Giai thich ro: custom provider dang goi qua OpenAI-compatible API voi model `qwen3-coder-480b-a35b-instruct`.

---

## Cau hoi thao luan

1. Tai sao `COPY requirements.txt` roi `RUN pip install` truoc `COPY source code`?
2. Khi nao nen bat `CHATBOT_MOCK_ONLY=true` de fallback sang mock?
3. Neu muon luu session qua nhieu container, in-memory session co con duoc khong?
