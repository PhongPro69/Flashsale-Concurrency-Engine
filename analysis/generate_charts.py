import sqlite3
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def analyze_and_plot():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flashsale.db")
    if not os.path.exists(db_path):
        print(f"Chưa tìm thấy database tại {db_path}. Hãy chạy server và test ít nhất 1 lần!")
        return

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM telemetry_logs ORDER BY id ASC", conn)
    conn.close()

    if df.empty:
        print("Chưa có dữ liệu log nào trong telemetry_logs. Hãy bắn test trước!")
        return

    print(f"Đã đọc {len(df)} dòng log từ database.")
    output_dir = os.path.dirname(__file__)

    # Set dark-themed styling for matplotlib
    plt.style.use('dark_background')
    plt.rcParams['font.sans-serif'] = 'Arial'

    # Biểu đồ 1: Phân bố độ trễ (Latency Distribution) giữa Naive và Atomic
    plt.figure(figsize=(10, 5))
    for mode, color in [('naive', '#f43f5e'), ('atomic', '#10b981')]:
        sub = df[df['mode'] == mode]
        if not sub.empty:
            plt.hist(sub['latency_ms'], bins=30, alpha=0.6, label=f"Mode: {mode.upper()}", color=color)
            p50 = sub['latency_ms'].quantile(0.50)
            p99 = sub['latency_ms'].quantile(0.99)
            print(f"[{mode.upper()}] p50: {p50:.2f}ms | p99: {p99:.2f}ms")

    plt.title("Phân Bố Độ Trễ (Latency Distribution: Naive vs Atomic)", fontsize=13, pad=15)
    plt.xlabel("Độ trễ (ms)")
    plt.ylabel("Số lượng Request")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.2)
    chart1_path = os.path.join(output_dir, "latency_distribution.png")
    plt.savefig(chart1_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"✓ Đã lưu biểu đồ: {chart1_path}")

    # Biểu đồ 2: Tích lũy số vé bán thành công theo thời gian (Cumulative Success)
    plt.figure(figsize=(10, 5))
    for mode, color in [('naive', '#f43f5e'), ('atomic', '#10b981')]:
        sub = df[(df['mode'] == mode) & (df['status'] == 'SUCCESS')].copy()
        if not sub.empty:
            sub['cumulative_sold'] = range(1, len(sub) + 1)
            time_rel = sub['created_at'] - sub['created_at'].min()
            plt.plot(time_rel, sub['cumulative_sold'], label=f"{mode.upper()} (Tổng bán: {len(sub)})", color=color, linewidth=2)

    plt.axhline(y=100, color='#eab308', linestyle='--', label="Giới hạn kho: 100 vé")
    plt.title("Tiến Trình Mở Bán & Phát Hiện Bán Âm Vé (Cumulative Sold)", fontsize=13, pad=15)
    plt.xlabel("Thời gian kể từ request đầu tiên (giây)")
    plt.ylabel("Số lượng vé đã bán")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.2)
    chart2_path = os.path.join(output_dir, "overselling_comparison.png")
    plt.savefig(chart2_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"✓ Đã lưu biểu đồ: {chart2_path}")

if __name__ == "__main__":
    analyze_and_plot()
