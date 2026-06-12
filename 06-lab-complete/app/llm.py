"""
LLM client — Google Gemini (Generative Language API).

- Có GEMINI_API_KEY  → gọi Gemini thật (model từ settings.llm_model).
- Không có key        → fallback mock LLM (chạy offline, không tốn tiền).

Dùng stdlib `urllib` để không thêm dependency nặng.
"""
import json
import logging
import urllib.request
import urllib.error

from app.config import settings

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def provider() -> str:
    """Trả về 'gemini' nếu có key, ngược lại 'mock'."""
    return "gemini" if settings.gemini_api_key else "mock"


def ask(question: str) -> str:
    """Hỏi LLM. Tự fallback mock khi không có key hoặc khi gọi lỗi."""
    key = settings.gemini_api_key
    if not key:
        from utils.mock_llm import ask as mock_ask
        return mock_ask(question)

    url = _GEMINI_URL.format(model=settings.llm_model)
    payload = json.dumps({
        "contents": [{"parts": [{"text": question}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 512},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (urllib.error.URLError, KeyError, IndexError, ValueError) as e:
        logger.warning(json.dumps({"event": "llm_error", "error": str(e)}))
        # Fallback an toàn để API không trả 500 khi Gemini lỗi
        from utils.mock_llm import ask as mock_ask
        return f"[Gemini tạm lỗi, dùng mock] {mock_ask(question)}"
