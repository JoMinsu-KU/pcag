"""
PCAG 서비스 상태 확인
=====================
실행 중인 모든 서비스의 상태를 확인합니다.

conda activate pcag && python scripts/check_services.py
"""
import httpx
import sys

SERVICES = {
    "Gateway Core":    "http://localhost:8000/docs",
    "Safety Cluster":  "http://localhost:8001/docs",
    "Policy Store":    "http://localhost:8002/v1/policies/active",
    "Sensor Gateway":  "http://localhost:8003/v1/assets/reactor_01/snapshots/latest",
    "OT Interface":    "http://localhost:8004/docs",
    "Evidence Ledger": "http://localhost:8005/docs",
    "Policy Admin":    "http://localhost:8006/v1/admin/health",
}

def check():
    print("PCAG Service Health Check")
    print("=" * 50)
    
    all_ok = True
    for name, url in SERVICES.items():
        try:
            resp = httpx.get(url, timeout=3.0)
            status = "OK" if resp.status_code < 500 else f"ERROR ({resp.status_code})"
            print(f"  [{status}] {name} ({url})")
        except httpx.ConnectError:
            print(f"  [DOWN] {name} ({url})")
            all_ok = False
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            all_ok = False
    
    print()
    if all_ok:
        print("All services are running!")
    else:
        print("Some services are not running. Start with:")
        print("  python scripts/start_services.py")

if __name__ == "__main__":
    check()
