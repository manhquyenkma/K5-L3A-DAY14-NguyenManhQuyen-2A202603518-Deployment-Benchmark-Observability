"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Không ping Redis lúc import để container vẫn khởi động được khi Redis chưa sẵn sàng.
"""
import redis

from app.config import settings


def _create_client():
    if not settings.redis_url:
        return None
    try:
        return redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
    except Exception:
        return None


r = _create_client()


def redis_healthy() -> bool:
    """Kiểm tra Redis cho GET /ready; lỗi kết nối hoặc chưa cấu hình → False."""
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False


def close_redis() -> None:
    """Đóng connection pool khi shutdown."""
    if r is not None:
        try:
            r.close()
        except Exception:
            pass
