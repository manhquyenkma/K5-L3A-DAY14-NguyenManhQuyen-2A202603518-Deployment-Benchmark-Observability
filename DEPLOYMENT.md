# Deployment Information

## Public URL
[CẦN ĐIỀN URL PUBLIC SAU KHI DEPLOY LÊN RAILWAY HOẶC RENDER, vd: https://your-agent.up.railway.app]

## Platform
[Railway / Render]

## Test Commands

### 1. Health Check (200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://YOUR_DOMAIN/health"
```

### 2. Readiness Check (200 — đã kết nối Redis trên cloud)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://YOUR_DOMAIN/ready"
```

### 3. API Test — Không có key (401)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://YOUR_DOMAIN/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### 4. API Test — Có API Key (200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://YOUR_DOMAIN/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- `PORT` (do nền tảng cấp tự động)
- `ENVIRONMENT=production`
- `REDIS_URL` (trỏ tới Redis service trên nền tảng)
- `AGENT_API_KEY` (đặt trên dashboard/CLI, không commit vào Git)
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `MONTHLY_BUDGET_USD=10.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
