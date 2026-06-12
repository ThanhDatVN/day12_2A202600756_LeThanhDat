"""
Cost guard — chặn chi tiêu vượt ngân sách.

Ước lượng chi phí token và cộng dồn theo ngày. Khi chạm
settings.daily_budget_usd thì trả 503 cho tới khi sang ngày mới (reset).
Trong production nhiều instance, lưu _daily_cost vào Redis để chia sẻ.
"""
import time

from fastapi import HTTPException

from app.config import settings

# Giá tham khảo gpt-4o-mini (USD / 1K tokens)
_INPUT_COST_PER_1K = 0.00015
_OUTPUT_COST_PER_1K = 0.0006

_daily_cost = 0.0
_cost_reset_day = time.strftime("%Y-%m-%d")


def check_and_record_cost(input_tokens: int, output_tokens: int) -> None:
    """
    Cộng chi phí ước lượng vào tổng trong ngày.
    Raise 503 nếu đã vượt ngân sách ngày.
    """
    global _daily_cost, _cost_reset_day

    today = time.strftime("%Y-%m-%d")
    if today != _cost_reset_day:
        _daily_cost = 0.0
        _cost_reset_day = today

    if _daily_cost >= settings.daily_budget_usd:
        raise HTTPException(503, "Daily budget exhausted. Try tomorrow.")

    cost = (input_tokens / 1000) * _INPUT_COST_PER_1K + \
           (output_tokens / 1000) * _OUTPUT_COST_PER_1K
    _daily_cost += cost


def current_cost() -> float:
    """Tổng chi phí đã ghi nhận trong ngày (USD)."""
    return _daily_cost
