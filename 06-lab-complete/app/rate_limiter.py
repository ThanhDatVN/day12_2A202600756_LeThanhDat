"""
Rate limiting — Sliding window (60 giây).

Mặc định dùng in-memory (đủ cho 1 instance / lab). Khi scale nhiều
instance, thay bằng Redis sorted-set để chia sẻ state giữa các replica.
Giới hạn lấy từ settings.rate_limit_per_minute.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings

# key -> deque các timestamp request trong cửa sổ 60s
_rate_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    """
    Sliding window: đếm số request của `key` trong 60 giây gần nhất.
    Raise 429 nếu vượt settings.rate_limit_per_minute.
    """
    now = time.time()
    window = _rate_windows[key]

    # bỏ các timestamp cũ hơn 60s
    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
            headers={"Retry-After": "60"},
        )

    window.append(now)
