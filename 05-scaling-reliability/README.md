# Section 5 — Scaling & Reliability

## Mục tiêu học
- Thêm health check và readiness probe trước khi deploy
- Graceful shutdown khi platform gửi `SIGTERM`
- Hiểu tại sao state trong memory sẽ vỡ khi scale ngang
- Chuyển session storage sang Redis để agent stateless
- Dùng Nginx để load balance nhiều agent instances

---

## Ví dụ Basic — Health Check + Graceful Shutdown

```text
develop/
├── app.py
├── requirements.txt
└── utils/mock_llm.py
```

### Chạy thử
```bash
cd 05-scaling-reliability/develop
pip install -r requirements.txt
python app.py
```

Test:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Graceful shutdown:
```bash
kill -SIGTERM <PID>
```

---

## Ví dụ Advanced — Stateless Agent + Redis + Nginx

```text
production/
├── app.py
├── Dockerfile
├── requirements.txt
├── docker-compose.yml
├── nginx.conf
└── test_stateless.py
```

### Chạy thử
```bash
cd /home/tungnguyen/Programming/Day12-Nguyen_Lam_Tung-2A202600173
docker compose -f 05-scaling-reliability/production/docker-compose.yml up --build --scale agent=3
```

Test:
```bash
curl http://localhost:8080/health
python 05-scaling-reliability/production/test_stateless.py
```

Điểm cần quan sát:
- `served_by` có thể khác nhau giữa các request
- session history vẫn còn nguyên vì state nằm trong Redis

Dừng stack:
```bash
docker compose -f 05-scaling-reliability/production/docker-compose.yml down
```

---

## Ý chính

1. Health check trả lời câu hỏi “container còn sống không?”
2. Readiness probe trả lời câu hỏi “instance đã sẵn sàng nhận traffic chưa?”
3. Graceful shutdown giúp request đang chạy xong hẳn trước khi process tắt.
4. Stateless design là bắt buộc khi một user có thể bị route tới nhiều instances khác nhau.
