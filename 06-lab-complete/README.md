# Lab 12 — Complete Production Agent

Kết hợp toàn bộ Day 12 vào một app cuối cùng:
- API key authentication
- Rate limiting `10 req/min`
- Monthly cost guard `$10/month`
- Multi-turn chat với session memory
- Redis-backed stateless session storage
- Health + readiness checks
- Structured logging
- Graceful shutdown
- Browser UI tại `/ui`
- Deploy configs cho Docker, Railway, và Render

---

## Cấu Trúc

```text
06-lab-complete/
├── app/
│   ├── main.py          # Final FastAPI app
│   ├── config.py        # 12-factor settings
│   ├── auth.py          # API key auth
│   ├── rate_limiter.py  # 10 req/min sliding window
│   ├── cost_guard.py    # $10/month budget guard
│   └── session_store.py # Redis-backed session storage
├── utils/
│   ├── provider_wrapper.py
│   ├── mock_llm.py
│   ├── chat_ui.html
│   └── ui_assets.py
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── render.yaml
├── .env.example
├── .dockerignore
└── requirements.txt
```

---

## Chạy Local

```bash
cd 06-lab-complete
cp .env.example .env.local
```

Điền các biến tối thiểu:
- `AGENT_API_KEY`
- `SHOPAIKEY_API_KEY` nếu muốn live custom provider

Chạy với Docker Compose:

```bash
docker compose up --build
```

Mở UI:

```text
http://localhost:8000/ui
```

Test health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Test protected API:

```bash
API_KEY=$(grep AGENT_API_KEY .env.local | cut -d= -f2)

curl -X POST http://localhost:8000/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","question":"Explain graceful shutdown briefly."}'
```

Test `/ask` alias:

```bash
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","question":"What is Redis used for?"}'
```

---

## Deploy Railway

```bash
cd 06-lab-complete
railway login
railway init
railway variables set AGENT_API_KEY=your-secret-key
railway variables set SHOPAIKEY_API_KEY=your-provider-key
railway variables set CUSTOM_PROVIDER_MODEL=qwen3-coder-480b-a35b-instruct
railway variables set CHATBOT_DEFAULT_PROVIDER=custom
railway variables set REDIS_URL=redis://...
railway up
```

Nếu chưa có Redis trên Railway, có thể tạm bật:

```bash
railway variables set ALLOW_IN_MEMORY_SESSIONS=true
```

Nhưng đó chỉ nên dùng cho demo ngắn, không phải production thật.

---

## Deploy Render

1. Push repo lên GitHub.
2. Render Dashboard → `New` → `Blueprint`.
3. Connect repo → Render đọc `render.yaml`.
4. Set secrets:
   - `SHOPAIKEY_API_KEY`
   - `AGENT_API_KEY`
   - `REDIS_URL`
5. Deploy.

---

## Kiểm Tra Production Readiness

```bash
python check_production_ready.py
```

Checker này xác nhận các phần cốt lõi của final project trước khi nộp bài.
