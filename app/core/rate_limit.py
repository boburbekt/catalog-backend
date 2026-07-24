import time
from collections import defaultdict, deque


class InProcessRateLimiter:
    """Oddiy, jarayon ichidagi sliding-window limiter.

    DIQQAT: holat faqat shu jarayon xotirasida saqlanadi. Bir nechta worker/replika bo‘lsa,
    har biri o‘z hisobini yuritadi — global cheklov emas. Ishonchli, taqsimlangan limit uchun
    Redis kabi tashqi do‘kon kerak (MVP doirasida qo‘shilmagan).
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(
        self, key: str, max_requests: int, window_seconds: float, now: float | None = None
    ) -> bool:
        """`key` uchun so‘rovga ruxsat bo‘lsa `True`, limit oshsa `False` qaytaradi."""
        if max_requests <= 0:
            return False
        current = time.monotonic() if now is None else now
        cutoff = current - window_seconds
        hits = self._hits[key]
        # Oynadan chiqib ketgan eski urinishlarni tozalaymiz.
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= max_requests:
            return False
        hits.append(current)
        return True

    def reset(self) -> None:
        """Barcha hisoblarni tozalaydi (asosan testlar uchun)."""
        self._hits.clear()


# Jarayon bo‘yicha bitta umumiy limiter — buyurtma endpointi shundan foydalanadi.
order_rate_limiter = InProcessRateLimiter()
