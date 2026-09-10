import time
import uuid
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd

from app.database import (
    init_db, reset_inventory, get_inventory_status, 
    record_order, record_telemetry, get_recent_telemetry, 
    get_connection
)
from app.redis_client import redis_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động: Khởi tạo bảng và đồng bộ số vé ban đầu
    init_db()
    reset_inventory(100)
    redis_manager.reset_stock(100)
    yield

app = FastAPI(
    title="Flash-Sale Concurrency Engine",
    description="Hệ thống mô phỏng bán vé tải cao, so sánh Race Condition vs Redis Atomic",
    lifespan=lifespan
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class BuyRequest(BaseModel):
    user_id: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h3>Dashboard HTML đang được tải...</h3>")

@app.get("/api/status")
async def get_status():
    """Lấy số liệu tồn kho, đơn hàng và các log mới nhất."""
    db_stats = get_inventory_status()
    redis_stock = redis_manager.get_stock()
    recent_logs = get_recent_telemetry(30)
    return {
        "db": db_stats,
        "redis_stock": redis_stock,
        "is_fake_redis": redis_manager.is_fake,
        "recent_logs": recent_logs
    }

@app.post("/api/reset")
async def reset_system(stock: int = Query(100, ge=1, le=10000), clear_logs: bool = Query(True)):
    """Reset kho vé về số lượng ban đầu và xóa đơn cũ."""
    reset_inventory(stock, clear_logs=clear_logs)
    redis_manager.reset_stock(stock)
    return {"message": f"Đã đặt lại kho vé về {stock} (clear_logs={clear_logs})."}

@app.post("/api/buy-naive")
async def buy_naive(payload: BuyRequest = BuyRequest()):
    """
    KỊCH BẢN 1: Cách làm ngây thơ (Gây Race Condition).
    Đọc DB -> Kiểm tra > 0 -> Trừ 1 -> Ghi DB.
    Khi nhiều người cùng gọi, sẽ xảy ra tranh chấp dữ liệu và BÁN ÂM VÉ.
    """
    req_id = str(uuid.uuid4())[:8]
    user_id = payload.user_id or f"user_{req_id}"
    start_time = time.perf_counter()

    # 1. Đọc số lượng vé hiện tại từ SQLite
    with get_connection() as conn:
        row = conn.execute("SELECT remaining_stock FROM inventory WHERE item_id = 1").fetchone()
        current_stock = row["remaining_stock"] if row else 0

    # 2. Giả lập độ trễ xử lý (network / logic kiểm tra ví / cổng thanh toán) 25ms
    # Đây là điểm chết: trong 25ms này, hàng chục request khác cũng đã đọc được current_stock cũ!
    await asyncio.sleep(0.025)

    # 3. Kiểm tra và trừ vé
    if current_stock > 0:
        with get_connection() as conn:
            conn.execute("UPDATE inventory SET remaining_stock = remaining_stock - 1 WHERE item_id = 1")
            conn.commit()
        record_order(user_id, mode="naive")
        status = "SUCCESS"
        msg = "Mua vé thành công (Chế độ Naive)!"
    else:
        status = "SOLD_OUT"
        msg = "Rất tiếc, đã hết vé!"

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    record_telemetry(req_id, user_id, mode="naive", status=status, latency_ms=duration_ms)

    return {
        "status": status,
        "message": msg,
        "user_id": user_id,
        "latency_ms": duration_ms
    }

@app.post("/api/buy-atomic")
async def buy_atomic(payload: BuyRequest = BuyRequest()):
    """
    KỊCH BẢN 2: Cách chuẩn mực dùng Redis Atomic Operation (Lua Script).
    Trừ vé tức thì trong RAM của Redis trước.
    Tuyệt đối KHÔNG BAO GIỜ bán âm vé.
    """
    req_id = str(uuid.uuid4())[:8]
    user_id = payload.user_id or f"user_{req_id}"
    start_time = time.perf_counter()

    # Trừ vé nguyên tử trong Redis
    remaining = redis_manager.atomic_decrement()

    if remaining >= 0:
        # Mua thành công -> Ghi đơn hàng vào database
        record_order(user_id, mode="atomic")
        status = "SUCCESS"
        msg = f"Mua vé thành công! Vé còn lại: {remaining}"
    else:
        status = "SOLD_OUT"
        msg = "Rất tiếc, vé đã hết sạch!"

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    record_telemetry(req_id, user_id, mode="atomic", status=status, latency_ms=duration_ms)

    return {
        "status": status,
        "message": msg,
        "remaining_stock": max(0, remaining),
        "user_id": user_id,
        "latency_ms": duration_ms
    }

@app.get("/api/export-csv")
async def export_logs_csv():
    """Xuất toàn bộ log telemetry ra file CSV để mở bằng Pandas trong Notebook."""
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM telemetry_logs ORDER BY id ASC", conn)
    
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    csv_path = os.path.join(logs_dir, "requests_log.csv")
    df.to_csv(csv_path, index=False)
    
    return FileResponse(csv_path, media_type="text/csv", filename="requests_log.csv")
