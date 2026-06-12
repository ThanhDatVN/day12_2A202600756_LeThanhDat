# Deployment Information

> **Student:** Le Thanh Dat — 2A202600756
> ✅ Đã deploy & verify live ngày 2026-06-12 (Railway, mock LLM).

## Public URL

```
https://day12-lethanhdat-2a202600756-production.up.railway.app
```

## Platform

Railway  *(hoặc Render / Cloud Run — chọn 1, xoá phần thừa)*

## Test Commands

### Health Check
```bash
curl https://day12-lethanhdat-2a202600756-production.up.railway.app/health
# Expected: {"status":"ok", ...}
```

### Readiness
```bash
curl https://day12-lethanhdat-2a202600756-production.up.railway.app/ready
# Expected: {"ready":true}
```

### API Test — KHÔNG có key (phải 401)
```bash
curl -i -X POST https://day12-lethanhdat-2a202600756-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# Expected: HTTP/1.1 401
```

### API Test — CÓ key (phải 200)
```bash
curl -X POST https://day12-lethanhdat-2a202600756-production.up.railway.app/ask \
  -H "X-API-Key: dat-day12-2A202600756-key" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is deployment?"}'
# Expected: 200 + {"question":...,"answer":...,"model":...}
```

### Rate limit (gửi 25 lần → xuất hiện 429)
> Deploy chạy `--workers 2`, rate-limiter in-memory theo từng worker nên ngưỡng
> hiệu dụng ~2× (đúng bài học stateless ở Part 5 — production nên dùng Redis).
```bash
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code} " -X POST \
    https://day12-lethanhdat-2a202600756-production.up.railway.app/ask \
    -H "X-API-Key: dat-day12-2A202600756-key" -H "Content-Type: application/json" \
    -d '{"question":"test"}'
done; echo
# Expected: ... 200 200 429 429 ...
```

## Environment Variables Set

| Biến | Giá trị | Ghi chú |
|------|---------|---------|
| `PORT` | (Railway tự inject) | |
| `ENVIRONMENT` | `production` | bật chế độ prod, ẩn `/docs` |
| `AGENT_API_KEY` | `<secret>` | **bắt buộc** — key auth |
| `JWT_SECRET` | `<secret>` | bắt buộc khi ENVIRONMENT=production |
| `RATE_LIMIT_PER_MINUTE` | `10` | giới hạn req/phút |
| `DAILY_BUDGET_USD` | `5.0` | ngân sách cost guard |
| `REDIS_URL` | `<redis-url>` | nếu bật Redis (stateless) |
| `GEMINI_API_KEY` | `<secret>` | key Google Gemini — để trống thì fallback mock |
| `LLM_MODEL` | `gemini-3.1-flash-lite` | model LLM thật |

> Không commit giá trị thật. Set trực tiếp trên dashboard Railway/Render.

## Giao diện web (UI)

Mở **https://day12-lethanhdat-2a202600756-production.up.railway.app/** trên trình duyệt:
nhập API key (`AGENT_API_KEY`) vào ô trên cùng → chat trực tiếp với agent.
Backend gọi **Google Gemini 3.1 Flash Lite** qua endpoint bảo mật `/ask`.

## Screenshots

- ![Deployment dashboard](screenshots/dashboard.png)
- ![Service running](screenshots/running.png)
- ![Test results](screenshots/test.png)

## Self-Test Checklist (verify 2026-06-12)

- [x] `/health` trả 200
- [x] `/ready` trả 200
- [x] `/ask` không key → 401
- [x] `/ask` có key → 200 + answer
- [x] Spam request → 429
- [ ] Test được từ thiết bị/máy khác *(bạn tự kiểm tra trên điện thoại)*
- [ ] Chụp 3 screenshot bỏ vào `screenshots/`
