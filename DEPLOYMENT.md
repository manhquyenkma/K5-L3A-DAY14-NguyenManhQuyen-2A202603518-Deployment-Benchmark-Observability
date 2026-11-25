# Deployment Information

## Public URL
https://k5-l3a-day14-nguyenmanhquyen-2a202603518-deploym-production.up.railway.app

## Platform
Railway (Docker + Railway Redis)

## Test Commands

### 1. Health Check (200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://k5-l3a-day14-nguyenmanhquyen-2a202603518-deploym-production.up.railway.app/health"
# Expected: 200
```

### 2. Readiness Check (200 — đã kết nối Redis trên cloud)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://k5-l3a-day14-nguyenmanhquyen-2a202603518-deploym-production.up.railway.app/ready"
# Expected: 200
```

### 3. API Test — Không có key (401)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://k5-l3a-day14-nguyenmanhquyen-2a202603518-deploym-production.up.railway.app/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 401
```

### 4. API Test — Có API Key (200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://k5-l3a-day14-nguyenmanhquyen-2a202603518-deploym-production.up.railway.app/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: 200
```

## Environment Variables Set
- `PORT=8000`
- `ENVIRONMENT=production`
- `REDIS_URL=${{Redis.REDIS_URL}}`
- `AGENT_API_KEY` (đặt trên Railway Variables, không commit vào Git)
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `MONTHLY_BUDGET_USD=10.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
