#!/usr/bin/env python
"""
Quick test script to verify Azure Monitor integration
Run this after starting your app to generate test telemetry
"""

import time
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8080"

def test_monitoring():
    print("🧪 Testing Cenaris Monitoring Integration\n")
    print("=" * 60)
    
    # Test 1: Basic connectivity
    print("\n1️⃣ Testing basic connectivity...")
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"   ✅ App is running (Status: {response.status_code})")
    except Exception as e:
        print(f"   ❌ App not running: {e}")
        print("   👉 Start your app first: python run.py")
        return
    
    # Test 2: Generate HTTP traffic
    print("\n2️⃣ Generating HTTP traffic (50 requests)...")
    success_count = 0
    error_count = 0
    
    def make_request(i):
        try:
            r = requests.get(BASE_URL, timeout=5)
            return r.status_code < 400
        except:
            return False
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(make_request, range(50)))
        success_count = sum(results)
        error_count = len(results) - success_count
    
    print(f"   ✅ Successful requests: {success_count}")
    print(f"   ❌ Failed requests: {error_count}")
    
    # Test 3: Test error tracking
    print("\n3️⃣ Testing error tracking...")
    try:
        # Try to trigger a 404
        response = requests.get(f"{BASE_URL}/nonexistent-page", timeout=5)
        print(f"   ✅ 404 error tracked (Status: {response.status_code})")
    except Exception as e:
        print(f"   ⚠️  Error test failed: {e}")
    
    # Test 4: Verify metrics generation
    print("\n4️⃣ Metrics that should now be in Azure Monitor:")
    print("   📊 HTTP Request Duration")
    print("   📊 HTTP Request Count")
    print("   📊 System CPU Usage")
    print("   📊 System Memory Usage")
    print("   📊 System Disk Usage")
    
    print("\n" + "=" * 60)
    print("\n✅ Test complete! Now check Azure Portal:\n")
    print("1. Go to: https://portal.azure.com")
    print("2. Find your Application Insights resource")
    print("3. Click 'Metrics' in left menu")
    print("4. Wait 2-3 minutes for data to appear")
    print("5. Look for metrics starting with 'http.server' and 'system'")
    print("\n🔍 To query logs:")
    print("1. Click 'Logs' in left menu")
    print("2. Run query:")
    print("   requests")
    print("   | where timestamp > ago(10m)")
    print("   | project timestamp, name, resultCode, duration")
    print("   | order by timestamp desc")
    print("\n💡 Tip: Data may take 2-5 minutes to appear in Azure Portal")

if __name__ == "__main__":
    test_monitoring()
