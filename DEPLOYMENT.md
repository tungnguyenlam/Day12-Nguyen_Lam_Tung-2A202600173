# Deployment Information

> Student Name: Nguyen Lam Tung  
> Student ID: 2A202600173  
> Date: 2026-04-17

## Public URL

Primary deployment target:
- Railway

Public URL:
- `https://<replace-with-your-railway-domain>.up.railway.app`

Before submission, replace the placeholder above with the actual value returned by:

```bash
railway domain
```

## Platform

- Platform: Railway
- Runtime style: Dockerfile deploy
- Shared app entrypoint: `cloud_app.py`
- Backing application: same FastAPI app used in `02-docker/production/main.py`

## Deployment Configuration

### Railway

Relevant files:
- `railway.toml`
- `cloud_app.py`
- `.github/workflows/railway-deploy.yml`

Required environment variables:
- `PORT`
- `SHOPAIKEY_API_KEY`
- `CUSTOM_PROVIDER_MODEL=qwen3-coder-480b-a35b-instruct`
- `CHATBOT_DEFAULT_PROVIDER=custom`
- `CHATBOT_MOCK_ONLY=false`
- `CHATBOT_ALLOW_MOCK_FALLBACK=true`

Optional variables:
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`

GitHub Actions secret:
- `RAILWAY_TOKEN`

### Final App (`06-lab-complete`)

If you deploy the complete final lab app instead of the shared cloud wrapper, also set:
- `AGENT_API_KEY`
- `REDIS_URL`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10.0`
- `ALLOW_IN_MEMORY_SESSIONS=false`

## Test Commands

Replace `<PUBLIC_URL>` and `<API_KEY>` before running.

### Health Check

```bash
curl https://<PUBLIC_URL>/health
```

Expected shape:

```json
{"status":"ok"}
```

### Provider Metadata

```bash
curl https://<PUBLIC_URL>/providers
```

### Chat Test

```bash
curl -X POST https://<PUBLIC_URL>/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","question":"Explain Docker in one short paragraph."}'
```

### Follow-up Turn

Use the returned `session_id`:

```bash
curl -X POST https://<PUBLIC_URL>/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","session_id":"<SESSION_ID>","question":"What did I ask before?"}'
```

### Final App Protected API Test (`06-lab-complete`)

```bash
curl -X POST https://<PUBLIC_URL>/ask \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","question":"Hello"}'
```

Expected behavior:
- Missing API key -> `401`
- Wrong API key -> `403`
- Valid API key -> `200`

### Rate-Limit Check (`06-lab-complete`)

```bash
for i in {1..12}; do
  curl -X POST https://<PUBLIC_URL>/ask \
    -H "X-API-Key: <API_KEY>" \
    -H "Content-Type: application/json" \
    -d '{"provider":"custom","question":"rate limit test"}'
done
```

Expected behavior:
- Requests above the configured limit eventually return `429`

## Local Demo Commands for Lecturer

### Part 2 Docker stack

```bash
docker compose -f 02-docker/production/docker-compose.yml up --build
```

Demo URLs:
- `http://localhost:8080/ui`
- `http://localhost:8080/docs`
- `http://localhost:8080/providers`

Presentation flow:
1. Open `/ui`
2. Select `custom`
3. Ask a first question
4. Ask a follow-up using the same session
5. Open `/providers` to show the wrapper selection

### Part 6 final app

```bash
cd 06-lab-complete
cp .env.example .env.local
docker compose up --build
```

Demo URLs:
- `http://localhost:8000/ui`
- `http://localhost:8000/health`
- `http://localhost:8000/ready`

Presentation flow:
1. Open `/ui`
2. Enter the `AGENT_API_KEY`
3. Choose `custom`
4. Ask one question
5. Ask a follow-up to show multi-turn memory
6. Explain that session state is stored in Redis, not only in process memory

## Verification Notes

Completed locally in the repository:
- `python -m compileall 04-api-gateway 05-scaling-reliability 06-lab-complete`
- `python 06-lab-complete/check_production_ready.py`

Result:
- `06-lab-complete` readiness checker passed `100%`

## Screenshots

Add real screenshots before submission in the `screenshots/` folder:
- `screenshots/railway-dashboard.png`
- `screenshots/public-url-health.png`
- `screenshots/final-ui.png`
- `screenshots/rate-limit-proof.png`

Placeholder note:
- If you only have the current local placeholder image, replace it with real captures from your deployed service before submitting.
