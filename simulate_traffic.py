import asyncio
import time
import argparse
import httpx
import numpy as np
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

async def send_buy_request(client: httpx.AsyncClient, base_url: str, mode: str, user_id: str, semaphore: asyncio.Semaphore):
    async with semaphore:
        start = time.perf_counter()
        try:
            resp = await client.post(
                f"{base_url}/api/buy-{mode}",
                json={"user_id": user_id},
                timeout=10.0
            )
            data = resp.json()
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": data.get("status", "ERROR"),
                "latency_ms": latency
            }
        except Exception as e:
            return {
                "status": "EXCEPTION",
                "latency_ms": (time.perf_counter() - start) * 1000
            }

async def run_traffic_simulation(base_url: str, mode: str, total_requests: int, concurrency: int):
    print(f"\n========================================================")
    print(f"🚀 BẮT ĐẦU BẮN TẢI: KỊCH BẢN [{mode.upper()}]")
    print(f"   Tổng số request: {total_requests} | Concurrency: {concurrency}")
    print(f"   Mục tiêu: Bán 100 vé VIP")
    print(f"========================================================")

    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)

    async with httpx.AsyncClient(limits=limits) as client:
        start_total = time.perf_counter()
        tasks = [
            send_buy_request(client, base_url, mode, f"buyer_{i+1}", semaphore)
            for i in range(total_requests)
        ]
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_total

    # Thống kê kết quả
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    sold_out_count = sum(1 for r in results if r["status"] == "SOLD_OUT")
    errors_count = sum(1 for r in results if r["status"] in ("ERROR", "EXCEPTION"))
    latencies = [r["latency_ms"] for r in results]

    p50 = np.percentile(latencies, 50)
    p90 = np.percentile(latencies, 90)
    p99 = np.percentile(latencies, 99)
    rps = total_requests / total_time

    print("\n📊 KẾT QUẢ THỰC NGHIỆM:")
    print(f"   • Thời gian hoàn thành: {total_time:.2f} giây")
    print(f"   • Throughput đạt được : {rps:.1f} req/s (RPS)")
    print(f"   • Số vé mua THÀNH CÔNG: {success_count}")
    print(f"   • Số request BỊ TỪ CHỐI (Hết vé): {sold_out_count}")
    print(f"   • Lỗi mạng / Exception: {errors_count}")
    print(f"\n⏱ PHÂN BỐ ĐỘ TRỄ (Latency):")
    print(f"   • p50 (Trung vị)      : {p50:.2f} ms")
    print(f"   • p90                 : {p90:.2f} ms")
    print(f"   • p99 (Trường hợp tệ) : {p99:.2f} ms")

    print("\n🔍 ĐÁNH GIÁ TÍNH ĐÚNG ĐẮN (DATA CONSISTENCY):")
    if mode == "naive":
        if success_count > 100:
            oversold = success_count - 100
            print(f"   ❌ PHÁT HIỆN BÁN ÂM VÉ! Bán lố {oversold} vé (Vượt {oversold}% tồn kho)!")
            print(f"   -> Nguyên nhân: Race Condition do truy vấn SQLite truyền thống không khóa luồng.")
        else:
            print(f"   ⚠️ Chưa phát hiện bán âm (thử tăng --concurrency lên 100).")
    else:
        if success_count == 100:
            print(f"   ✅ TUYỆT VỜI: Bán chính xác 100/100 vé! Zero Overselling.")
            print(f"   -> Nhờ cơ chế Redis Atomic Lua Script đảm bảo kiểm tra và trừ tồn kho đơn luồng.")
        else:
            print(f"   ℹ️ Bán được {success_count} vé.")
    print(f"========================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mô phỏng bắn tải kiểm tra Race Condition")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000", help="FastAPI Server URL")
    parser.add_argument("--mode", type=str, choices=["naive", "atomic"], default="naive", help="Kịch bản test: naive hoặc atomic")
    parser.add_argument("--requests", type=int, default=500, help="Tổng số request gửi đi")
    parser.add_argument("--concurrency", type=int, default=50, help="Số kết nối đồng thời")
    args = parser.parse_args()

    asyncio.run(run_traffic_simulation(args.url, args.mode, args.requests, args.concurrency))
