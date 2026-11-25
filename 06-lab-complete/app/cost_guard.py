"""
Cost guard (tiêu chí 8) — Cộng dồn chi phí token vào Redis và chặn khi vượt budget.
"""
import threading
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_mem_lock = threading.Lock()
_mem_daily: dict[str, float] = {}
_mem_monthly: dict[str, float] = {}


def _keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f"cost:daily:{now.strftime('%Y-%m-%d')}", f"cost:monthly:{now.strftime('%Y-%m')}"


def check_budget() -> None:
    """Kiểm tra ngân sách ngày/tháng trước khi gọi LLM. Vượt → HTTP 402."""
    daily_key, monthly_key = _keys()
    daily_spent = 0.0
    monthly_spent = 0.0

    if r is not None:
        try:
            daily_val, monthly_val = r.mget(daily_key, monthly_key)
            daily_spent = float(daily_val or 0.0)
            monthly_spent = float(monthly_val or 0.0)
        except Exception:
            with _mem_lock:
                daily_spent = _mem_daily.get(daily_key, 0.0)
                monthly_spent = _mem_monthly.get(monthly_key, 0.0)
    else:
        with _mem_lock:
            daily_spent = _mem_daily.get(daily_key, 0.0)
            monthly_spent = _mem_monthly.get(monthly_key, 0.0)

    if daily_spent >= settings.daily_budget_usd or monthly_spent >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Budget exceeded",
                "daily_spent_usd": round(daily_spent, 6),
                "daily_budget_usd": settings.daily_budget_usd,
                "monthly_spent_usd": round(monthly_spent, 6),
                "monthly_budget_usd": settings.monthly_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Cộng chi phí request vào Redis và trả về chi phí (USD)."""
    cost = (
        (input_tokens / 1000.0) * PRICE_INPUT_PER_1K
        + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    )
    daily_key, monthly_key = _keys()

    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.incrbyfloat(daily_key, cost)
            pipe.expire(daily_key, 48 * 3600)
            pipe.incrbyfloat(monthly_key, cost)
            pipe.expire(monthly_key, 35 * 24 * 3600)
            pipe.execute()
            return cost
        except Exception:
            pass

    with _mem_lock:
        _mem_daily[daily_key] = _mem_daily.get(daily_key, 0.0) + cost
        _mem_monthly[monthly_key] = _mem_monthly.get(monthly_key, 0.0) + cost
    return cost
