import sqlite3
import time
import os
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flashsale.db")

def get_connection() -> sqlite3.Connection:
    """Tạo kết nối SQLite với timeout và WAL mode để tránh database is locked khi test tải."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    """Khởi tạo cấu trúc các bảng."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Bảng tồn kho
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                item_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                total_stock INTEGER NOT NULL,
                remaining_stock INTEGER NOT NULL
            );
        """)
        # Bảng đơn hàng đã ghi nhận
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        # Bảng telemetry để phục vụ phân tích dữ liệu độ trễ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        # Khởi tạo mặc định 100 vé nếu chưa có
        cursor.execute("SELECT COUNT(*) as count FROM inventory WHERE item_id = 1")
        if cursor.fetchone()["count"] == 0:
            cursor.execute("""
                INSERT INTO inventory (item_id, name, total_stock, remaining_stock)
                VALUES (1, 'Vé VIP Concert', 100, 100)
            """)
        conn.commit()

def reset_inventory(stock: int = 100, clear_logs: bool = True):
    """Đặt lại số lượng vé và xóa các đơn hàng cũ để sẵn sàng test lại."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE inventory 
            SET total_stock = ?, remaining_stock = ? 
            WHERE item_id = 1
        """, (stock, stock))
        cursor.execute("DELETE FROM orders")
        if clear_logs:
            cursor.execute("DELETE FROM telemetry_logs")
        conn.commit()

def get_inventory_status() -> Dict[str, Any]:
    """Lấy trạng thái kho vé và số lượng đơn hàng đã bán theo từng mode."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory WHERE item_id = 1")
        inv = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE mode = 'naive'")
        naive_orders = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE mode = 'atomic'")
        atomic_orders = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM telemetry_logs")
        total_requests = cursor.fetchone()["cnt"]

        return {
            "total_stock": inv["total_stock"] if inv else 100,
            "db_remaining_stock": inv["remaining_stock"] if inv else 0,
            "naive_orders": naive_orders,
            "atomic_orders": atomic_orders,
            "total_requests": total_requests
        }

def record_order(user_id: str, mode: str, item_id: int = 1):
    """Ghi nhận đơn hàng thành công vào database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (user_id, item_id, mode, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, item_id, mode, time.time()))
        conn.commit()

def record_telemetry(request_id: str, user_id: str, mode: str, status: str, latency_ms: float):
    """Ghi nhận log đo lường từng request để phân tích Data Science."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO telemetry_logs (request_id, user_id, mode, status, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (request_id, user_id, mode, status, latency_ms, time.time()))
        conn.commit()

def get_recent_telemetry(limit: int = 25) -> List[Dict[str, Any]]:
    """Lấy các log mới nhất để hiển thị trực tiếp lên live terminal trên dashboard."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT request_id, user_id, mode, status, latency_ms, created_at
            FROM telemetry_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
