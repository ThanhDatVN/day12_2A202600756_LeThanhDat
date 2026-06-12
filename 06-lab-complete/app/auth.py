"""
Authentication — API Key.

Cách dùng trong endpoint:
    from app.auth import verify_api_key
    @app.post("/ask")
    def ask(_key: str = Depends(verify_api_key)):
        ...
"""
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# auto_error=False để tự trả message rõ ràng thay vì 403 mặc định
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Kiểm tra header `X-API-Key` khớp với AGENT_API_KEY trong env.
    Trả về api_key nếu hợp lệ, raise 401 nếu thiếu/sai.
    """
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key
