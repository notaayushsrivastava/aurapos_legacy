"""
Concurrency & Load Testing Suite for AuraPOS
Tests simultaneous concurrent user traffic across critical routes.
"""

import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure root dir is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import app

def test_concurrent_traffic(num_users=30, requests_per_user=10):
    print(f"\n=======================================================")
    print(f">> Starting Concurrency Test: {num_users} Concurrent Users")
    print(f"=======================================================")

    results = []
    errors = []
    latencies = []

    def simulate_user_session(user_id):
        user_latencies = []
        client_ip = f"10.0.{user_id // 254}.{(user_id % 254) + 1}"
        with app.app.test_client() as client:
            client.environ_base['REMOTE_ADDR'] = client_ip
            # 1. Login
            t0 = time.perf_counter()
            resp = client.post('/login', data={'username': 'admin@aurasalon.com', 'password': 'password'})
            t1 = time.perf_counter()
            user_latencies.append(t1 - t0)
            if resp.status_code not in (200, 302):
                errors.append(f"User {user_id} login failed: {resp.status_code}")

            # 2. Sequential browsing & API requests
            for _ in range(requests_per_user):
                # Health check
                t0 = time.perf_counter()
                h_resp = client.get('/healthz')
                t1 = time.perf_counter()
                user_latencies.append(t1 - t0)
                if h_resp.status_code != 200:
                    errors.append(f"Health check failed: {h_resp.status_code}")

                # Dashboard
                t0 = time.perf_counter()
                d_resp = client.get('/dashboard')
                t1 = time.perf_counter()
                user_latencies.append(t1 - t0)
                if d_resp.status_code != 200:
                    errors.append(f"Dashboard failed: {d_resp.status_code}")

                # Reports API
                t0 = time.perf_counter()
                r_resp = client.get('/api/reports?from=2026-08-01&to=2026-09-30')
                t1 = time.perf_counter()
                user_latencies.append(t1 - t0)
                if r_resp.status_code != 200:
                    errors.append(f"Reports API failed: {r_resp.status_code}")

                # Bills API
                t0 = time.perf_counter()
                b_resp = client.get('/api/bills?limit=20')
                t1 = time.perf_counter()
                user_latencies.append(t1 - t0)
                if b_resp.status_code != 200:
                    errors.append(f"Bills API failed: {b_resp.status_code}")

        return user_latencies

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [executor.submit(simulate_user_session, i) for i in range(num_users)]
        for f in as_completed(futures):
            try:
                lat = f.result()
                latencies.extend(lat)
            except Exception as e:
                errors.append(str(e))

    total_time = time.perf_counter() - start_time
    total_requests = len(latencies)
    rps = total_requests / total_time if total_time > 0 else 0

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] * 1000 if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] * 1000 if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] * 1000 if latencies else 0
    avg_latency = (sum(latencies) / len(latencies)) * 1000 if latencies else 0

    print(f"\n[+] Concurrency Test Results:")
    print(f"   - Total Concurrent Users: {num_users}")
    print(f"   - Total Requests Handled: {total_requests}")
    print(f"   - Total Test Duration:    {total_time:.2f}s")
    print(f"   - Throughput:             {rps:.2f} req/sec")
    print(f"   - Latency (Avg):          {avg_latency:.2f} ms")
    print(f"   - Latency (p50):          {p50:.2f} ms")
    print(f"   - Latency (p95):          {p95:.2f} ms")
    print(f"   - Latency (p99):          {p99:.2f} ms")
    print(f"   - Error Count:            {len(errors)}")

    if errors:
        print("\n[!] Encountered Errors:")
        for err in errors[:10]:
            print(f"   - {err}")
    else:
        print("\n[SUCCESS] 100% Success Rate under simultaneous load!")

    assert len(errors) == 0, f"Encountered {len(errors)} errors during concurrency test"

if __name__ == '__main__':
    test_concurrent_traffic(num_users=25, requests_per_user=5)
