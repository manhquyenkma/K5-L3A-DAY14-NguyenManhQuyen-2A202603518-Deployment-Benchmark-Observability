# Day 14 Lab — Mission Answers

> Mọi giải thích code, số đo và kết quả kiểm thử đều được lấy từ mã nguồn và các lần chạy thực tế trên máy cá nhân, GitHub Codespaces và Railway.

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`
1. **Hardcode secrets trong code (dòng 17–18):** `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` — nếu push lên GitHub sẽ lộ secret ngay lập tức.
2. **Hardcode cấu hình & bật debug (dòng 21–22, 53):** `DEBUG = True`, `MAX_TOKENS = 500`, `reload=True` — không thay đổi được theo môi trường (dev/staging/prod).
3. **Dùng `print()` và log lộ secret (dòng 33–34, 38):** in plain text ra stdout và in thẳng `OPENAI_API_KEY` ra log, khó tổng hợp/tìm kiếm và gây rò rỉ thông tin nhạy cảm.
4. **Không có health check endpoint:** thiếu `/health` (liveness) và `/ready` (readiness), khiến platform/load balancer không biết khi nào app treo hoặc chưa sẵn sàng.
5. **Hardcode `host="localhost"` và `port=8000` (dòng 51–52):** chỉ lắng nghe loopback nên bên ngoài container không truy cập được, và không đọc `PORT` do cloud platform inject.
6. **Không xử lý graceful shutdown:** khi nhận `SIGTERM`, process tắt đột ngột có thể cắt ngang request đang xử lý.

### Exercise 1.2: Kết quả chạy bản `develop`
```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -i -X POST "http://localhost:8000/ask?question=Hello"
```
Kết quả thực tế khi chạy `uvicorn app:app` và gọi `POST /ask?question=Hello`:
```http
HTTP/1.1 200
content-type: application/json
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```
**Quan sát:** Endpoint trả `200` và hoạt động trên local, nhưng chưa production-ready vì còn các anti-pattern đã liệt kê ở Exercise 1.1 (hardcode secret, log thẳng `OPENAI_API_KEY`, bind `localhost`, bật `reload=True`, không có `/health` và `/ready`).

### Exercise 1.3: So sánh `develop/app.py` và `production/app.py`

| Feature | Develop (`develop/app.py`) | Production (`production/app.py` & `config.py`) | Tại sao quan trọng? |
|---|---|---|---|
| Config & Secrets | Hardcode trực tiếp (`OPENAI_API_KEY`, `DATABASE_URL`, `MAX_TOKENS`, `DEBUG = True`) | Đọc từ biến môi trường qua `Settings` (`os.getenv`), fail-fast khi thiếu key ở production (`config.py:42-43`) | Tuân thủ 12-Factor, tránh lộ secret lên Git và đổi cấu hình giữa dev/staging/prod không cần sửa code |
| Host & Port | Cố định `host="localhost"`, `port=8000`, `reload=True` | `host=settings.host` (`0.0.0.0`), `port=settings.port` (đọc `PORT`), `reload=settings.debug` | Container/cloud bắt buộc bind `0.0.0.0` và dùng `PORT` do platform cấp |
| Health check | Không có | Có `GET /health` (liveness), `GET /ready` (readiness, trả 503 nếu chưa sẵn sàng) và `GET /metrics` | Platform/LB kiểm tra tình trạng sống & khả năng nhận traffic trước khi route request |
| Logging | `print(...)` plain text, log luôn cả API key | `logging` xuất structured JSON (`json.dumps(...)`), không log secret | Dễ parse/truy vấn trên Loki, Datadog, Cloud Logging và an toàn bảo mật |
| Shutdown | Tắt đột ngột | Dùng FastAPI `lifespan` + `signal.signal(signal.SIGTERM, handle_sigterm)` để hoàn thành request đang chạy | Không làm rớt request của người dùng khi deploy/restart container |

---

## Part 2: Docker

### Exercise 2.1: Đọc `02-docker/develop/Dockerfile`
1. **Base image:** `python:3.11` (full Debian + Python distribution, dung lượng lớn ~1 GB).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY 02-docker/develop/requirements.txt .` và `pip install` đứng trước `COPY 02-docker/develop/app.py .`?** Để tận dụng **Docker layer cache**: khi chỉ sửa code trong `app.py` mà `requirements.txt` không đổi, Docker tái sử dụng cache layer cài thư viện thay vì chạy lại `pip install`.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?** `ENTRYPOINT` định nghĩa lệnh thực thi chính cố định của container, còn `CMD` cung cấp lệnh/tham số mặc định (có thể bị ghi đè dễ dàng khi truyền tham số lúc `docker run`).

### Exercise 2.2: Build và chạy container `develop`
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
curl -i -X POST "http://localhost:8000/ask?question=What+is+Docker%3F"
```
```http
HTTP/1.1 200 OK
content-type: application/json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build & so sánh dung lượng (`02-docker/production/Dockerfile`)
- **Stage 1 (`builder`):** dùng `python:3.11-slim`, cài công cụ build (`gcc`, `libpq-dev`) và cài dependencies vào `/root/.local` bằng `pip install --no-cache-dir --user`.
- **Stage 2 (`runtime`):** khởi tạo từ `python:3.11-slim` sạch, chỉ copy `/root/.local` và mã nguồn cần thiết, tạo non-root user `appuser`, cấu hình `HEALTHCHECK` và chạy `uvicorn`.
- **Tại sao image nhỏ hơn?** Loại bỏ hoàn toàn `gcc`, `libpq-dev`, cache build và các công cụ biên dịch không cần thiết khi chạy runtime.
- **Kích thước đo bằng `docker images`:**
  - Develop (`my-agent:develop`): `1.67 GB` (`1670 MB`)
  - Production (`my-agent:advanced`): `240 MB`
  - Difference: giảm `~85.6%` (`1430 MB`)

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)
- **Sơ đồ kiến trúc:**
  ```text
  Client (:80) ─▶ Nginx (reverse proxy, rate limit 10r/s) ─▶ Agent (:8000, runtime)
                                                                 ├──▶ Redis (:6379, cache/rate limit)
                                                                 └──▶ Qdrant (:6333, vector DB)
  (Tất cả các service giao tiếp nội bộ qua bridge network `internal` bằng tên service DNS)
  ```
- **Kết quả test qua Nginx:**
  ```http
  # GET http://localhost/health
  HTTP/1.1 200 OK
  Server: nginx
  Content-Type: application/json
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  X-XSS-Protection: 1; mode=block

  {"status":"ok","uptime_seconds":10.3,"version":"2.0.0","timestamp":"2026-11-25T17:42:04.997620"}

  # POST http://localhost/ask
  HTTP/1.1 200 OK
  Server: nginx
  Content-Type: application/json
  Content-Length: 103
  ```

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy Agent Part 6 (`06-lab-complete/`)
- **Public URL:** https://k5-l3a-day14-nguyenmanhquyen-2a202603518-deploym-production.up.railway.app
- **Kiểm tra 4 lệnh CP6:** `/health` → `200`, `/ready` → `200`, `POST /ask` không key → `401`, `POST /ask` có key → `200`.
- **Screenshots:** xem `DEPLOYMENT.md` và thư mục `screenshots/` (`dashboard.png`, `running.png`, `test.png`).

### So sánh `railway.toml` và `render.yaml`
- **Định dạng & phạm vi:** `railway.toml` dùng cú pháp TOML, tập trung cấu hình build (`builder = "DOCKERFILE"`) và deploy (`healthcheckPath`, `restartPolicyType`) cho 1 service; trong khi `render.yaml` là Blueprint YAML (Infrastructure-as-Code) có thể khai báo cùng lúc nhiều tài nguyên (`type: web` + `type: redis` managed).
- **Quản lý biến môi trường & secret:** Railway cấu hình env/secret qua Dashboard hoặc CLI (`railway variables set`) và nối Redis qua biến tham chiếu trên nền tảng; Render cho phép khai báo trực tiếp trong `render.yaml` với `generateValue: true` (tự sinh secret), `sync: false` (nhập tay trên dashboard, không lộ vào Git) và `fromService` để lấy `connectionString` từ managed Redis.
- **Runtime & scale:** Railway nhận diện `Dockerfile` theo `builder = "DOCKERFILE"` và inject `PORT`; Render chỉ định `runtime: docker`, `plan`, `region`, `healthCheckPath: /health` và hỗ trợ auto-deploy từ nhánh Git khi Blueprint thay đổi.

### Exercise 3.3: Pipeline CI/CD Cloud Run (`cloudbuild.yaml` & `service.yaml`)
Pipeline trong `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` gồm 4 bước tuần tự (`waitFor`):
1. **`test`:** dùng image `python:3.11-slim` cài `requirements.txt` + `pytest` và chạy `pytest tests/`.
2. **`build`:** build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from`).
3. **`push`:** đẩy cả hai tag image lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **`deploy`:** dùng `gcloud run deploy` triển khai image theo `$COMMIT_SHA` lên Cloud Run (`asia-southeast1`, `min-instances=1`, `max-instances=10`, memory `512Mi`) và gắn secret từ Google Secret Manager; kết hợp với `service.yaml` khai báo Knative Service (`containerConcurrency: 80`, `livenessProbe` `/health`, `startupProbe` `/ready`).

---

## Part 4: API Security

### Exercise 4.1–4.3: Test Authentication & Rate Limiting (`04-api-gateway/`)
- **Exercise 4.1 (`develop/app.py`):** API key được kiểm tra qua dependency `verify_api_key` dùng `APIKeyHeader(name="X-API-Key")` so sánh với `os.getenv("AGENT_API_KEY")`. Nếu thiếu key trả `401`, sai key trả `403`. Để rotate key an toàn mà không downtime, có thể hỗ trợ tạm thời danh sách key hợp lệ (key cũ + key mới) qua env var rồi gỡ key cũ sau khi client cập nhật.
- **Exercise 4.2 & 4.3 (`production/app.py`, `rate_limiter.py`):**
  - Thuật toán: **Sliding Window Counter** lưu timestamps trong `deque` theo `user_id` (`rate_limiter.py:29-72`).
  - Giới hạn: user thường (`rate_limiter_user`) = **10 requests / 60 giây**, admin (`rate_limiter_admin`) = **100 requests / 60 giây**.
  - Phân biệt theo role: ở `app.py:141` chọn `rate_limiter_admin if role == "admin" else rate_limiter_user` (hoặc đặt ngưỡng cao hơn / skip check cho role admin).
- **Kết quả kiểm thử thực tế (401 / 200 / 429 — đã che token):**

  **Exercise 4.1 (`develop/app.py` với `AGENT_API_KEY=secret-key-123`):**
  ```http
  # Không có X-API-Key
  HTTP/1.1 401
  content-type: application/json
  {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

  # Có X-API-Key: secret-key-123
  HTTP/1.1 200
  content-type: application/json
  {"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
  ```

  **Exercise 4.2 & 4.3 (`production/app.py`, đăng nhập `student` / `demo123` — giới hạn 10 req/phút):**
  ```http
  # Gọi /ask không có JWT
  HTTP/1.1 401
  content-type: application/json
  {"detail":"Authentication required. Include: Authorization: Bearer <token>"}

  # Lấy token từ POST /auth/token (đã che token)
  HTTP/1.1 200
  content-type: application/json
  {"access_token":"<MASKED_TOKEN>","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."}

  # Gọi /ask với Authorization: Bearer <MASKED_TOKEN> (request #1)
  HTTP/1.1 200
  content-type: application/json
  {"question":"Explain JWT","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}

  # Burst các request tiếp theo (vòng lặp 2..12)
  Req #2: HTTP 200 | {"question":"Test 2",...,"usage":{"requests_remaining":8,"budget_remaining_usd":4e-05}}
  ...
  Req #10: HTTP 200 | {"question":"Test 10",...,"usage":{"requests_remaining":0,"budget_remaining_usd":0.000193}}
  Req #11: HTTP 429 | Retry-After=54 | {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":54}}
  Req #12: HTTP 429 | Retry-After=53 | {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":53}}
  ```

### Exercise 4.4: Cách làm Cost Guard (`cost_guard.py` & Redis)
- Tính chi phí dựa trên số `input_tokens` và `output_tokens` nhân với đơn giá từng 1K tokens (`PRICE_INPUT_PER_1K`, `PRICE_OUTPUT_PER_1K`).
- **Trước khi gọi LLM (`check_budget`):** đọc tổng chi tiêu ngày/tháng hiện tại từ Redis (`cost:daily:<YYYY-MM-DD>`, `cost:monthly:<YYYY-MM>`). Nếu đã đạt hoặc vượt ngưỡng (`DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`), từ chối ngay bằng **HTTP 402 Payment Required** để không tốn tiền gọi LLM.
- **Sau khi gọi LLM (`record_cost`):** cộng dồn chi phí phát sinh vào Redis bằng `INCRBYFLOAT` và đặt `EXPIRE` tương ứng theo chu kỳ ngày/tháng để state dùng chung cho mọi worker/instance và tự reset ở chu kỳ mới.

---

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation Notes & Test Results (`05-scaling-reliability/`)
- **Liveness (`/health`) vs Readiness (`/ready`):** `/health` kiểm tra process còn sống (trả `200` ngay cả khi phụ thuộc tạm mất kết nối, tránh platform restart container liên tục khi Redis chập chờn); `/ready` kiểm tra khả năng sẵn sàng phục vụ traffic (ping Redis — nếu lỗi trả `503` để load balancer ngừng route request mới vào instance đó).
- **Graceful shutdown:** khi nhận `SIGTERM`, server ngừng nhận kết nối mới, chờ các request in-flight xử lý xong rồi mới đóng kết nối Redis và thoát với exit code `0`.
- **Stateless design với Redis:** không lưu conversation history hay rate-limit state trong RAM của từng process; mọi instance đọc/ghi chung vào Redis nên khi scale lên 3 instance sau Nginx load balancer (`round-robin`), request liên tiếp rơi vào các instance khác nhau (`served_by` thay đổi) vẫn giữ nguyên lịch sử hội thoại.
- **Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python test_stateless.py`:**
  ```text
  ============================================================
  Stateless Scaling Demo
  ============================================================

  Session ID: 2f715d62-f06b-41ec-bf21-f00a501b877a

  Request 1: [instance-b4eaf7]
  Request 2: [instance-fbc78d]
  Request 3: [instance-b18723]
  Request 4: [instance-b4eaf7]
  Request 5: [instance-fbc78d]

  Total requests: 5
  Instances used: {'instance-fbc78d', 'instance-b18723', 'instance-b4eaf7'}
  ✅ All requests served despite different instances!

  --- Conversation History ---
  Total messages: 10
  ✅ Session history preserved across all instances via Redis!
  ```

---

## Part 6: Checklist Deliverable (`check_production_ready.py`)

Kết quả chạy đầy đủ trên GitHub Codespaces (Python 3.11 + Docker 29.9.2-2, image `238 MB`, `docker stop` `0.4s`):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI log

1. **Hỏi gì:** Nhờ hỗ trợ hướng dẫn và thực hiện hoàn chỉnh các phần có thể làm được của bài lab Day 14 (`06-lab-complete/`, `benchmark-observability/`, các câu hỏi Part 1–5 và báo cáo nộp bài).
2. **Nhận gì:**
   - Khôi phục các file khung và tài liệu gốc bị thiếu từ Git `HEAD` (bao gồm 2 file Grafana provisioning có đường dẫn dài trên Windows).
   - Hoàn thiện mã nguồn Part 6 (`app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`) và sửa `KNOWLEDGE_BASE` trong `06-lab-complete/benchmark-observability/develop/utils/mock_llm.py` cho Exercise 7.3 (`security-02`, `scaling-03`).
   - Tạo môi trường ảo cài đủ thư viện để chạy kiểm thử thật cho Part 1, Part 4, Part 6 (`--skip-docker`) và toàn bộ Part 7 Bước 1 (`eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`, 4 mức `load_v2_c*.json` và 3 mức `load_v2_slow_*.json`), copy vào `reports/` và cập nhật số liệu thật vào `MISSION_ANSWERS.md`, `BENCHMARK_REPORT.md`.
3. **Tự sửa và tự kiểm tra:**
   - Đã xác minh trực tiếp kết quả chạy `check_production_ready.py --static-only` (28/28), `check_production_ready.py --skip-docker` (36/37 — chỉ thiếu Redis/Docker/WSL2), `eval_v2_fixed` (23/23, 100%, `Quality gate ✅ PASS`), và 7 file `load_test.py` trong `reports/`.
   - Đã tự chạy và xác minh toàn bộ trên GitHub Codespaces (`check_production_ready.py` đạt `PASS 12/12 · 43/43`, Docker Part 2 & Part 5, Part 7 Bước 2 Observability + Locust) và deploy thành công lên Railway kèm Redis cloud.
