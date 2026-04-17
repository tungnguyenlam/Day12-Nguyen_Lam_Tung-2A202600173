# Cloud Run Deployment Using The 02-Docker App

Cloud Run trong section nay deploy **chinh app production** o `02-docker/production/main.py`.
Khong co mot app rieng cho cloud nua.

## Build

```bash
gcloud builds submit --config 03-cloud-deployment/production-cloud-run/cloudbuild.yaml .
```

## Secret

```bash
echo -n "YOUR_SHOPAIKEY_API_KEY" | \
gcloud secrets create shopaikey-api-key --data-file=-
```

Neu secret da ton tai:

```bash
echo -n "YOUR_SHOPAIKEY_API_KEY" | \
gcloud secrets versions add shopaikey-api-key --data-file=-
```

## Deploy

```bash
gcloud run deploy ai-agent \
  --image gcr.io/PROJECT_ID/ai-agent:latest \
  --region asia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production,CHATBOT_DEFAULT_PROVIDER=custom,CUSTOM_PROVIDER_MODEL=qwen3-coder-480b-a35b-instruct,CHATBOT_MOCK_ONLY=false \
  --set-secrets SHOPAIKEY_API_KEY=shopaikey-api-key:latest
```

## Endpoints

- `/ui`
- `/docs`
- `/providers`
- `/chat`
- `/health`
