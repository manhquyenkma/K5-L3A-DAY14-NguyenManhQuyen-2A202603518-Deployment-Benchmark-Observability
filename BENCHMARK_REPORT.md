# Benchmark & Observability Report — Day 14

> Toàn bộ số liệu được lấy trực tiếp từ kết quả chạy `load_test.py` (`reports/*.json`), `eval/run_eval.py`, Locust headless (`benchmark-results/*.csv`), Grafana, Jaeger và Prometheus.

**Họ tên:** Nguyen Manh Quyen
**MSSV:** 2A202603518
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11 (Python 3.11.9, FastAPI 0.115.0, Uvicorn 0.30.0 — Bước 1) · GitHub Codespaces (Docker 29.9.2-2, Docker Compose v5.6.1, Python 3.11.18 — Bước 2)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Latency cơ bản mock LLM ~120–180ms (+20ms retrieval ở v2, p50 ~200ms); ngưỡng 500ms đảm bảo trải nghiệm nhanh với 95% request mà không báo động giả vì 3% tail latency |
| Error rate `/ask` | < 2 % | Mock LLM có `MOCK_ERROR_RATE=0.01` (1%) mặc định; error budget 2% cho phép lỗi upstream ngắn hạn mà vẫn giữ độ tin cậy |
| Accuracy trên golden dataset | ≥ 80 % | Ngưỡng quality gate tối thiểu trước khi deploy/merge (v2 sau khi bổ sung Knowledge Base đạt 100% = 23/23) |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.9 | 206.8 | 251.7 | 1712.2 | 0.67% | PASS |
| 10 | 39.34 | 199.0 | 246.1 | 1699.1 | 0.67% | PASS |
| 50 | 42.55 | 343.7 | 4027.5 | 5302.2 | 1.67% | FAIL |
| 100 | 40.3 | 1406.7 | 5354.6 | 5750.8 | 0.33% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- **Không tăng tuyến tính ở concurrency cao.** Từ `concurrency=1` (3.9 req/s) lên `concurrency=10` (39.34 req/s), RPS tăng gần như tuyến tính (~10x) do các request chạy bất đồng bộ song song hiệu quả. Tuy nhiên từ `concurrency=10` lên `50` (42.55 req/s) và `100` (40.3 req/s), RPS bão hòa quanh ~40 req/s trong khi p95 tăng vọt từ 246.1 ms lên 4027.5 ms (`c=50`) và 5354.6 ms (`c=100`), dẫn tới FAIL SLO p95. Nguyên nhân là 1 process uvicorn đơn lẻ bị nghẽn ở event loop / hàng đợi kết nối và chi phí xử lý request (JSON logging, Prometheus metrics, middleware) khi đồng thời quá nhiều request đổ vào.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 197.9 | 237.4 | 248.9 |
| 0.03 (mặc định) | 236.9 | 267.1 | 1708.6 |
| 0.1 | 376.9 | 1703.1 | 1732.9 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **`p99` nhạy nhất với request chậm** (ở `MOCK_SLOW_RATE=0.03`, `p99` nhảy gần 7x từ `248.9 ms` lên `1708.6 ms` trong khi `avg` chỉ tăng từ `197.9 ms` lên `236.9 ms`). Khi `MOCK_SLOW_RATE=0.1` (10% request chậm), cả `p95` cũng vọt lên `1703.1 ms` (vượt SLO 500ms → FAIL), nhưng `avg` vẫn chỉ là `376.9 ms` (< 500ms). Vì vậy không nên đặt SLO theo `average`, vì giá trị trung bình bị đa số request nhanh kéo xuống và che giấu trải nghiệm rất tệ của nhóm người dùng gặp tail latency.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.9 | 109.1 | 113.6 |
| Tổng cost (USD) | $0.000415 | $0.000762 | $0.000790 |
| Cost / câu đúng (USD) | $0.00041535 | $0.00003627 | $0.00003436 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "api key", "xác thực"], ...)` giải thích JWT tự chứa claims, có hạn (`exp`) và chữ ký số (`signature`) vào `KNOWLEDGE_BASE` trong `06-lab-complete/benchmark-observability/develop/utils/mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["kubernetes", "hpa", "autoscaler"], ...)` giải thích HPA scale theo CPU, memory và custom metrics vào `KNOWLEDGE_BASE` trong `06-lab-complete/benchmark-observability/develop/utils/mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- Agent `v2` có thêm bước retrieval nên `Avg tokens / câu` tăng gần gấp đôi (`113.6` so với `57.9` ở `v1`), `Total cost` tăng từ `$0.000415` lên `$0.000790` và `p95` tăng nhẹ từ `197.5 ms` lên `242.9 ms` (+45.4 ms).
- Đổi lại, **Accuracy tăng từ 4.3% lên 100.0%** và **`Cost / câu đúng` giảm ~12.1 lần** (từ `$0.00041535` xuống `$0.00003436`). Đánh đổi thêm retrieval latency và token input là hoàn toàn xứng đáng.

**Quality gate trong CI/CD (Exercise 7.3):**
Khi chạy `python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json`, script trả về **exit code `1`** nếu `accuracy < --min-accuracy` hoặc có câu bị regression (ví dụ chạy v1 so với baseline v2 sẽ trả exit code `1`). Trong GitHub Actions, đặt lệnh này làm 1 step để chặn merge PR khi quality gate fail:

```yaml
- name: Eval Quality Gate
  run: |
    cd 06-lab-complete/benchmark-observability/develop
    AGENT_VERSION=v2 PORT=8002 python app.py &
    sleep 3
    python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json
```

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] `screenshots/grafana-dashboard.png` — Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [x] `screenshots/jaeger-slow-trace.png` — Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [x] `screenshots/jaeger-error-trace.png` — Một trace lỗi trong Jaeger (có event `exception`)
- [x] `screenshots/prometheus-alert-firing.png` — Trang Alerts của Prometheus với ít nhất 2 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1 phút 40 giây (PENDING sau ~25s) | Error rate (1% → ~19–21%) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2 phút 30 giây (PENDING sau ~40s) | Latency p95 / p99 (p95: ~0.4s → ~2.8s; p99: ~0.9s → ~3.5s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~2 phút 40 giây (PENDING sau ~45s) | Cost burn rate / LLM cost 1h (tăng ~5–10 lần) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~50 giây (PENDING sau ~10s) | Instances up (2 → 1; `up{job="agent"} = 0` cho 1 target) |
| E | `AGENT_VERSION=v1` | Không có alert firing | N/A | Retrieval hit ratio (~0), Tokens/s giảm, bảng Phiên bản (`v2` → `v1`) |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

- Chạy **eval quality gate** trên golden dataset trong CI/CD trước khi deploy (chặn ngay khi accuracy giảm hoặc có regression) và kết hợp **online evaluation / LLM-as-judge / phản hồi người dùng** + theo dõi chỉ số `retrieval_hit_ratio` và bảng version đang chạy trên Grafana.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `b8aa156fddb772831e1181e23e200e04`
- Tổng thời gian: `1713.5` ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1693.5` ms, `98.8%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T18:04:57.650370+00:00", "level": "INFO", "service": "observable-agent", "instance": "9ebb4484c203", "event": "llm_call", "trace_id": "b8aa156fddb772831e1181e23e200e04", "span_id": "0d39c324eda6b3e0", "request_id": "84641a9714d8", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 40, "cost_usd": 3.5e-05, "llm_ms": 1693.5}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 66.00 | 190 | 230 | 1700 | 72 (0.91%) |
| 3 | 65.72 | 190 | 230 | 1700 | 66 (0.84%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- **Không.** Khi scale từ 1 lên 3 instance, `p95` giữ nguyên `230 ms`, `p99` giữ nguyên `1700 ms` và throughput vẫn quanh ~66 req/s (`66.00` vs `65.72 req/s`). Nguyên nhân là vì agent chạy bất đồng bộ (`async`) nên 1 instance đã xử lý dư tải ~66 req/s từ 100 Locust users; nút thắt của từng request nằm ở **thời gian chờ mock LLM upstream** (`MOCK_LATENCY_MS` + `MOCK_SLOW_RATE`) chứ không phải do thiếu CPU/instance.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Latency trung bình (`avg`) che giấu tail latency; phải dùng `p95`/`p99` cho SLO và kết hợp load test để phát hiện điểm nghẽn concurrency (như ở `c=50`/`c=100` trong bài).
  2. Eval trên golden dataset với quality gate và chỉ số `cost / câu đúng` giúp đánh giá đúng giá trị của thay đổi (v2 đắt token hơn mỗi câu nhưng rẻ hơn ~12x trên mỗi câu đúng) và chặn regression trước khi deploy.
  3. Ba trụ cột Metrics – Traces – Logs liên kết với nhau (`Grafana` báo bất thường → `Jaeger` tìm span chậm/lỗi → lọc JSON log theo `trace_id`) giúp khoanh vùng nhanh lỗi do hạ tầng hay do upstream LLM.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Thêm giám sát ở tầng Nginx/API Gateway (đếm 504/429/402 vì request lỗi tại proxy chưa chắc tới được agent), synthetic health probe từ bên ngoài, và alert burn-rate cho error budget & chi phí LLM theo từng API key/tenant.
