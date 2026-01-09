"""
Quick performance test to measure typical request overhead.
Run this after starting the Flask dev server to see baseline timing.
"""
import requests
import time

BASE_URL = "http://localhost:8080"

# Simulate a logged-in session (you'll need to authenticate first manually or via OAuth)
session = requests.Session()

def measure_endpoint(url, name):
    """Measure response time for an endpoint."""
    start = time.time()
    try:
        resp = session.get(url, timeout=10)
        elapsed = time.time() - start
        print(f"{name:30s} {resp.status_code:3d}  {elapsed*1000:7.0f}ms")
        return elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"{name:30s} ERR  {elapsed*1000:7.0f}ms - {e}")
        return elapsed

if __name__ == "__main__":
    print("\nPerformance Benchmark (after manual login):")
    print("=" * 60)
    print(f"{'Endpoint':<30s} {'Status':>4s} {'Time':>8s}")
    print("-" * 60)
    
    # Test various endpoints
    endpoints = [
        ("/", "Homepage"),
        ("/dashboard", "Dashboard"),
        ("/evidence-repository", "Evidence Repository"),
        ("/profile", "Profile"),
        ("/ai-evidence", "AI Evidence"),
    ]
    
    total_time = 0
    for path, name in endpoints:
        elapsed = measure_endpoint(f"{BASE_URL}{path}", name)
        total_time += elapsed
        time.sleep(0.5)  # Small delay between requests
    
    print("-" * 60)
    print(f"Total time: {total_time*1000:.0f}ms")
    print(f"Average:    {(total_time/len(endpoints))*1000:.0f}ms")
