import httpx
import subprocess
import sys

base_url = "http://127.0.0.1:8000"

print("==================================================")
print("1. RESET TOAN BO (XOA SACH LOGS)")
print("==================================================")
r = httpx.post(f"{base_url}/api/reset?stock=100&clear_logs=true")
print(r.json())

print("\n==================================================")
print("2. BAN TAI KICH BAN NAIVE (300 req, concurrency 50)")
print("==================================================")
p1 = subprocess.run(
    [sys.executable, "simulate_traffic.py", "--mode", "naive", "--requests", "300", "--concurrency", "50"],
    capture_output=True, text=True, encoding="utf-8"
)
print(p1.stdout)

print("\n==================================================")
print("3. RESET KHO VE (GIU LAI LOGS DE SO SANH)")
print("==================================================")
r2 = httpx.post(f"{base_url}/api/reset?stock=100&clear_logs=false")
print(r2.json())

print("\n==================================================")
print("4. BAN TAI KICH BAN ATOMIC (300 req, concurrency 50)")
print("==================================================")
p2 = subprocess.run(
    [sys.executable, "simulate_traffic.py", "--mode", "atomic", "--requests", "300", "--concurrency", "50"],
    capture_output=True, text=True, encoding="utf-8"
)
print(p2.stdout)

print("\n==================================================")
print("5. XUAT 2 BIEU DO PHAN TICH (ANALYSIS CHARTS)")
print("==================================================")
p3 = subprocess.run(
    [sys.executable, "analysis/generate_charts.py"],
    capture_output=True, text=True, encoding="utf-8"
)
print(p3.stdout)
print("ALL BENCHMARK COMPLETED SUCCESSFULLY!")
