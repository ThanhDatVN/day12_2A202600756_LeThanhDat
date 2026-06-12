# Day 12 Lab — Mission Answers

> **Student Name:** Le Thanh Dat
> **Student ID:** 2A202600756
> **Date:** 2026-06-12

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

File phân tích: `01-localhost-vs-production/develop/app.py`

| # | Anti-pattern | Vì sao nguy hiểm |
|---|--------------|------------------|
| 1 | **Hardcode secrets** — `OPENAI_API_KEY = "sk-..."`, `DATABASE_URL = "...admin:password123..."` ngay trong code | Push lên GitHub là lộ key/mật khẩu ngay; không rotate được; lập tức bị scan bot lấy mất |
| 2 | **Không có config management** — `DEBUG = True`, `MAX_TOKENS = 500` cứng trong code | Muốn đổi cấu hình phải sửa code + redeploy; không tách được dev/staging/prod |
| 3 | **Dùng `print()` thay vì logging** — và còn `print(OPENAI_API_KEY)` | Không có log level/timestamp/structured; **in cả secret ra log** = lỗ hổng bảo mật |
| 4 | **Không có health check endpoint** | Agent crash thì platform (Railway/Render/K8s) không biết để restart hay ngừng route traffic |
| 5 | **Port + host cố định** — `host="localhost"`, `port=8000` | `localhost` không nhận kết nối ngoài container; cloud inject `PORT` qua env nên app sẽ không bind đúng |
| 6 | **`reload=True` trong production** | Hao RAM/CPU, không an toàn, chỉ dùng khi dev |
| 7 | **Không validate input** — `question: str` không giới hạn độ dài | Dễ bị abuse (payload khổng lồ) → tốn token/tiền |
| 8 | **Không graceful shutdown** | Khi platform gửi SIGTERM, request đang chạy bị cắt giữa chừng |

> **Tối thiểu yêu cầu 5 — đã tìm được 8.**

### Exercise 1.2: Run basic version

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
# POST /ask → trả lời được, NHƯNG: không health check, log lộ secret, port cứng.
```

Kết luận: **chạy được ≠ production-ready.**

### Exercise 1.3: Comparison table

So sánh `develop/app.py` ❌ với `production/app.py` ✅:

| Feature | Develop (basic) | Production (advanced) | Tại sao quan trọng? |
|---------|-----------------|-----------------------|---------------------|
| **Config** | Hardcode trong code | `config.py` đọc từ env vars (12-factor) | Đổi cấu hình không cần sửa code; tách dev/prod; không lộ secret |
| **Secrets** | `sk-...` hardcode + in ra log | Lấy từ `OPENAI_API_KEY` env, không log | Tránh lộ key khi push Git / xem log |
| **Health check** | ❌ Không có | ✅ `GET /health` + `GET /ready` | Platform biết khi nào restart / route traffic |
| **Logging** | `print()` (kèm secret) | JSON structured, không log secret | Parse được bởi Datadog/Loki; audit; bảo mật |
| **Host/Port** | `localhost:8000` cứng | `0.0.0.0` + `PORT` từ env | Chạy được trong container & trên cloud |
| **Shutdown** | Đột ngột (không bắt SIGTERM) | Graceful qua `lifespan` + `SIGTERM` handler | Hoàn thành request đang chạy, đóng connection sạch |
| **Reload** | `reload=True` luôn | Chỉ reload khi `DEBUG=true` | Production ổn định, tiết kiệm tài nguyên |
| **CORS** | ❌ Không | ✅ `allowed_origins` cấu hình được | Kiểm soát origin được phép gọi API |
| **Input validation** | `question: str` thô | Pydantic + kiểm tra rỗng (422) | Chặn input xấu, payload quá lớn |

### Checkpoint 1
- [x] Hiểu tại sao hardcode secrets là nguy hiểm
- [x] Biết cách dùng environment variables (12-factor)
- [x] Hiểu vai trò health check endpoint
- [x] Biết graceful shutdown là gì

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

File: `02-docker/develop/Dockerfile`

1. **Base image:** `python:3.11` — full Python distribution (~1 GB).
2. **Working directory:** `/app` (đặt bằng `WORKDIR /app`).
3. **Tại sao COPY `requirements.txt` trước code?** Tận dụng **Docker layer cache**: nếu requirements không đổi, Docker cache lại layer `pip install`. Chỉ khi đổi dependencies mới phải cài lại → build nhanh hơn nhiều khi chỉ sửa code.
4. **CMD vs ENTRYPOINT:**
   - `CMD` = lệnh **mặc định**, dễ bị override khi `docker run image <lệnh khác>`.
   - `ENTRYPOINT` = lệnh **cố định luôn chạy**; arg từ `docker run` được nối làm tham số.
   - Pattern hay dùng: `ENTRYPOINT` đặt binary, `CMD` đặt arg mặc định.

### Exercise 2.2 & 2.3: Image size comparison

Develop = single-stage `python:3.11` (full). Production = multi-stage `python:3.11-slim`, copy `--user` site-packages sang runtime, non-root, có HEALTHCHECK.

Lệnh đo thực tế (build từ **project root**):

```bash
docker build -f 02-docker/develop/Dockerfile    -t agent:develop .
docker build -f 02-docker/production/Dockerfile -t agent:production .
docker images | grep agent
```

| Image | Base | Kích thước (dự kiến¹) |
|-------|------|----------------------|
| Develop | `python:3.11` (full) | ~**1.0–1.1 GB** |
| Production | `python:3.11-slim` multi-stage | ~**180–250 MB** |
| **Difference** | | **~80% nhỏ hơn** |

> ¹ Số đo **thực tế** trên máy này: image multi-stage của Lab 06 (cùng pattern slim + multi-stage) = **247 MB** (< 500 MB ✓). Image develop full `python:3.11` ~1 GB. Bạn có thể chạy `docker images` để xác nhận lại.

**Tại sao production nhỏ hơn?**
- `slim` base nhỏ hơn full ~900 MB.
- **Multi-stage:** stage builder chứa `gcc`/build tools bị **vứt bỏ**, runtime chỉ copy site-packages đã build.
- `--no-cache-dir` không giữ cache pip.

### Exercise 2.4: Docker Compose stack

`02-docker/production/docker-compose.yml` thường gồm: **agent** (app) + **redis** (state/cache), giao tiếp qua mạng nội bộ của compose bằng **service name** (vd `redis://redis:6379`). `depends_on` + healthcheck đảm bảo thứ tự khởi động.

### Checkpoint 2
- [x] Hiểu cấu trúc Dockerfile
- [x] Biết lợi ích multi-stage build
- [x] Hiểu Docker Compose orchestration
- [x] Biết debug container (`docker logs`, `docker exec`)

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

- **Platform:** Railway (xem `06-lab-complete/railway.toml`)
- **URL:** **https://day12-lethanhdat-2a202600756-production.up.railway.app** (đã deploy & verify live 2026-06-12)
- **Screenshot:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`
- **Ghi chú deploy:** 2 bug đã sửa để chạy được trên Railway — (1) `utils/` không nằm trong build context → copy vào `06-lab-complete/utils/`; (2) `$PORT` không expand trong `startCommand` → bọc `sh -c`. Image production **247 MB** (< 500 MB ✓).

Lệnh:
```bash
cd 06-lab-complete
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=<secret> JWT_SECRET=<secret> ENVIRONMENT=production
railway up
railway domain
```

### Exercise 3.2: Render — `render.yaml` vs `railway.toml`

| | `railway.toml` | `render.yaml` |
|---|---|---|
| Định dạng | TOML | YAML |
| Cách deploy | CLI (`railway up`) | Blueprint từ GitHub repo |
| Khai báo env | `railway variables set` | block `envVars:` (có `generateValue`, `sync:false`) |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Auto-deploy | theo project | `autoDeploy: true` |

Điểm chung: đều trỏ Docker build, health check `/health`, restart policy.

### Checkpoint 3
- [x] Hiểu cách deploy lên ít nhất 1 platform
- [x] Có public URL hoạt động — https://day12-lethanhdat-2a202600756-production.up.railway.app
- [x] Hiểu cách set env vars trên cloud
- [x] Biết cách xem logs (`railway logs` / Render dashboard)

---

## Part 4: API Security

Test cục bộ chạy trên `06-lab-complete` (đã verify ngày 2026-06-12).

### Exercise 4.1: API Key authentication

- Key được kiểm tra trong dependency `verify_api_key` (`app/auth.py`), inject bằng `Depends`.
- Sai/thiếu key → **401** với message hướng dẫn header `X-API-Key`.
- Rotate key = đổi env `AGENT_API_KEY` rồi redeploy (không sửa code).

Kết quả test thực tế:
```text
# Không key
POST /ask  → 401   ✅
# Có key đúng
POST /ask  -H "X-API-Key: <key>" → 200 + answer   ✅
```

### Exercise 4.2: JWT (advanced)

Flow: `POST /token` (username/password) → server ký JWT bằng `JWT_SECRET` → client gửi `Authorization: Bearer <token>` → server verify chữ ký + hạn `exp`. Ưu điểm so với API key: token có hạn, mang được claims (user, role), không cần tra DB mỗi request.

### Exercise 4.3: Rate limiting

- **Algorithm:** Sliding window 60 giây (`app/rate_limiter.py`) — deque timestamp, loại bỏ mục cũ hơn 60s, so với `RATE_LIMIT_PER_MINUTE`.
- **Limit:** 10 req/phút mỗi key (cấu hình qua env).
- Vượt limit → **429** kèm header `Retry-After: 60`.
- Bypass cho admin: có thể whitelist key admin hoặc đặt limit riêng theo role.

Kết quả test thực tế (limit=10):
```text
200 200 200 200 200 200 200 200 200 200 429 429 ...   ✅
```

### Exercise 4.4: Cost guard implementation

Cách tiếp cận (`app/cost_guard.py`):
- Ước lượng token in/out → quy ra USD theo đơn giá model.
- Cộng dồn `_daily_cost`; chạm `DAILY_BUDGET_USD` → trả **503** "budget exhausted".
- Tự reset khi sang ngày mới.
- **Production nhiều instance:** thay biến memory bằng Redis (`INCRBYFLOAT budget:<user>:<month>`, `EXPIRE`) để chia sẻ state — mỗi user $10/tháng như mô tả lab.

### Checkpoint 4
- [x] Implement API key authentication
- [x] Hiểu JWT flow
- [x] Implement rate limiting
- [x] Implement cost guard (memory; nâng cấp Redis cho multi-instance)

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

- `GET /health` — **liveness**: process còn sống → 200 (kèm uptime, version). Fail → platform restart container.
- `GET /ready` — **readiness**: đã init xong/đủ dependency (Redis...) chưa. Chưa sẵn sàng → **503**, load balancer ngừng route traffic vào.
- Tách 2 cái vì: liveness=có nên restart không; readiness=có nên gửi traffic không. Khác nhau!

### Exercise 5.2: Graceful shutdown

- Bắt `SIGTERM` (`signal.signal(signal.SIGTERM, ...)`) + dùng `lifespan` để cleanup khi shutdown.
- Uvicorn chạy với `timeout_graceful_shutdown=30`: ngừng nhận request mới, để request đang chạy hoàn thành, rồi mới thoát.
- Quan trọng vì cloud rolling-deploy gửi SIGTERM liên tục; không graceful = drop request của user.

### Exercise 5.3: Stateless design

- **Anti-pattern:** lưu `conversation_history = {}` trong RAM → scale ra 3 instance thì mỗi instance có lịch sử riêng, request bị routing khác nhau sẽ mất context.
- **Đúng:** lưu state ngoài process — **Redis** (`history:<user_id>`). Mọi instance đọc chung → có thể scale ngang tuỳ ý, instance chết không mất dữ liệu.
- `REDIS_URL` đã có trong `config.py`; docker-compose có service `redis`.

### Exercise 5.4: Load balancing

`docker compose up --scale agent=3` → 3 instance agent, **Nginx** đứng trước phân tán request (round-robin). 1 instance chết → traffic dồn sang 2 instance còn lại (nhờ health check). Đây chính là architecture của Part 6.

### Exercise 5.5: Test stateless

`test_stateless.py`: tạo conversation → kill 1 instance ngẫu nhiên → gọi tiếp → vì state ở Redis nên **conversation vẫn còn**. Chứng minh thiết kế stateless hoạt động.

### Checkpoint 5
- [x] Implement health & readiness checks
- [x] Implement graceful shutdown
- [x] Hiểu refactor stateless (Redis)
- [x] Hiểu load balancing với Nginx
- [x] Hiểu cách test stateless

---

## Tổng kết Lab 06 (Final Project)

Chạy trình kiểm tra tự động:
```bash
cd 06-lab-complete
python check_production_ready.py
# Result: 20/20 checks passed (100%) — PRODUCTION READY
```

Đã verify cục bộ + trên URL live ngày 2026-06-12: `/health` 200 · auth 401/200 · rate-limit 429 · metrics OK.
Cấu trúc module: `app/main.py`, `config.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `llm.py`.

### Nâng cấp ngoài yêu cầu (bonus)
- **LLM thật:** tích hợp **Google Gemini 3.1 Flash Lite** (`app/llm.py`, gọi Generative Language API qua `x-goog-api-key`). Tự **fallback mock** khi không có key hoặc khi Gemini lỗi → không bao giờ trả 500.
- **Giao diện web chat** tại `GET /` (HTML thuần, không thêm dependency): nhập API key → chat trực tiếp; key được lưu ở `localStorage` của trình duyệt, không nhúng cứng trong HTML. Endpoint `/ask` vẫn yêu cầu `X-API-Key`.
- **Bảo mật key:** `GEMINI_API_KEY` chỉ đặt ở env (Railway dashboard / `.env.local`), không commit vào repo.
