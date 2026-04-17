# Section 3 — Cloud Deployment Options

Section nay deploy **cung mot app** voi `02-docker/production/main.py`.
Khong duy tri app rieng cho cloud nua.

## 3 Tier: Chọn Platform Theo Nhu Cầu

| Tier | Platform | Khi nào dùng | Thời gian deploy |
|------|----------|-------------|-----------------|
| 1 | Railway, Render | MVP, demo, học | < 10 phút |
| 2 | AWS ECS, Cloud Run | Production | 15–30 phút |
| 3 | Kubernetes | Enterprise, large-scale | Vài giờ setup |

---

## railway/ — Deploy < 5 Phút

Không cần server config. Kết nối GitHub → Auto deploy.

```
railway/
├── railway.toml        # Railway config
├── app.py              # Thin wrapper → same app as 02-docker
└── requirements.txt    # Reuse root/shared requirements
```

### Các bước deploy Railway:
1. `cd <repo-root>`  ← chạy từ project root, không phải từ `03-cloud-deployment/`
2. `railway login` (hoặc qua browser)
3. `railway init`
4. `railway service`  ← link hoặc tạo web service nếu CLI hỏi
5. `railway variables set SHOPAIKEY_API_KEY=...`
6. `railway variables set CUSTOM_PROVIDER_MODEL=qwen3-coder-480b-a35b-instruct`
7. `railway variables set CHATBOT_DEFAULT_PROVIDER=custom`
8. `railway variables set CHATBOT_MOCK_ONLY=false`
9. `railway up`
10. Nhận URL dạng `https://your-app.up.railway.app`

Sau deploy, demo ở:
- `https://your-app.up.railway.app/ui`
- `https://your-app.up.railway.app/docs`

### GitHub Actions cho Railway

Workflow da duoc them tai:

```
.github/workflows/railway-deploy.yml
```

Nó se:
1. Install Python deps tu `requirements.txt`
2. Smoke-test `cloud_app.py`
3. Install Railway CLI
4. Deploy len service `ai-agent` bang `railway up --ci --service ai-agent`

Can them GitHub secret:

```text
RAILWAY_TOKEN
```

Khuyen nghi dung **Project Token** scope vao environment can deploy.

---

## render/ — render.yaml (Infrastructure as Code)

Định nghĩa toàn bộ infrastructure trong 1 YAML file.

```
render/
└── render.yaml         # Deploy root cloud_app.py → same app as 02-docker
```

### Các bước deploy Render:
1. Push repo lên GitHub
2. Render Dashboard → `New` → `Blueprint`
3. Connect repo
4. Set secret `SHOPAIKEY_API_KEY`
5. Deploy

Sau deploy, demo ở:
- `https://your-render-app.onrender.com/ui`
- `https://your-render-app.onrender.com/docs`

---

## production-cloud-run/ — GCP Cloud Run + CI/CD

Production-grade. Tự động build và deploy khi push code.

```
production-cloud-run/
├── cloudbuild.yaml     # CI/CD pipeline
├── service.yaml        # Cloud Run service definition
└── README.md           # Hướng dẫn chi tiết
```

## Shared Cloud Entrypoint

Cloud platforms trong section nay dung:

```
cloud_app.py
```

File nay expose cung FastAPI app voi `02-docker/production/main.py`.

### Các bước deploy Cloud Run:
1. Tạo secret `shopaikey-api-key` trong Secret Manager
2. Chạy:

```bash
gcloud builds submit --config 03-cloud-deployment/production-cloud-run/cloudbuild.yaml .
```

3. Sau deploy, mở Cloud Run service URL:
- `/ui`
- `/docs`

---

## Câu hỏi thảo luận

1. Tại sao serverless (Lambda) không phải lúc nào cũng tốt cho AI agent?
2. "Cold start" là gì? Ảnh hưởng thế nào đến UX?
3. Khi nào nên upgrade từ Railway lên Cloud Run?
