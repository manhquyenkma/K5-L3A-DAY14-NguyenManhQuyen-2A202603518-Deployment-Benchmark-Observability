"""
API Key authentication (tiêu chí 6).

Kiểm tra header X-API-Key khớp với AGENT_API_KEY; thiếu hoặc sai → HTTP 401.
"""
import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Dependency xác thực X-API-Key cho các endpoint được bảo vệ."""
    expected = settings.agent_api_key
    if not expected or not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Provide header X-API-Key.",
        )
    return api_key
