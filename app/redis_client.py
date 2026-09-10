import os
import redis
import fakeredis
from typing import Optional

TICKET_KEY = "flashsale:ticket_stock:1"

# Lua script đảm bảo tính nguyên tử tuyệt đối (Atomic)
# 1. Đọc số vé hiện tại trong Redis
# 2. Nếu > 0 thì DECR và trả về số vé còn lại
# 3. Nếu <= 0 thì trả về -1 (Báo hết vé ngay trong RAM)
LUA_DECREMENT_SCRIPT = """
local stock = redis.call('GET', KEYS[1])
if not stock then
    return -1
end
if tonumber(stock) > 0 then
    return redis.call('DECR', KEYS[1])
else
    return -1
end
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class RedisManager:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        self.is_fake = False
        if redis_url:
            try:
                self.client = redis.Redis.from_url(redis_url, decode_responses=True)
                self.client.ping()
                print(f"[Redis] Connected to remote Redis: {redis_url[:15]}...")
            except Exception as e:
                print(f"[Redis] Connection failed ({e}), fallback to in-memory Fakeredis.")
                self.client = fakeredis.FakeRedis(decode_responses=True)
                self.is_fake = True
        else:
            print("[Redis] REDIS_URL not found -> Using in-memory Fakeredis (zero-setup).")
            self.client = fakeredis.FakeRedis(decode_responses=True)
            self.is_fake = True

    def reset_stock(self, count: int = 100):
        """Đặt lại số lượng vé trong Redis."""
        self.client.set(TICKET_KEY, count)

    def get_stock(self) -> int:
        """Lấy số lượng vé còn lại trong Redis."""
        val = self.client.get(TICKET_KEY)
        return max(0, int(val)) if val is not None else 0

    def atomic_decrement(self) -> int:
        """
        Trừ 1 vé một cách nguyên tử bằng lệnh DECR của Redis.
        Redis xử lý đơn luồng (single-threaded) nên lệnh DECR là atomic tuyệt đối.
        - Nếu số vé sau khi giảm >= 0: Mua thành công.
        - Nếu < 0: Đã hết vé -> Gọi INCR lại để giữ mức 0 và trả về -1 (SOLD_OUT).
        """
        remaining = self.client.decr(TICKET_KEY)
        if remaining >= 0:
            return remaining
        else:
            self.client.incr(TICKET_KEY)
            return -1

# Khởi tạo singleton instance
redis_manager = RedisManager()
