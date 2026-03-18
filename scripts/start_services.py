"""
PCAG 전체 서비스 런처
=====================
Safety Cluster를 제외한 모든 PCAG 서비스를 시작합니다.

Safety Cluster는 pcag-isaac 환경에서 별도 실행:
  conda activate pcag-isaac
  python scripts/start_safety_cluster.py

실행 방법 (conda pcag 환경):
  conda activate pcag
  python scripts/start_services.py

종료: Ctrl+C
"""
import subprocess
import sys
import time
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

# Safety Cluster(8001)는 pcag-isaac 환경에서 별도 실행
SERVICES = [
    ("Policy Store",    "pcag.apps.policy_store.main:app",    8002),
    ("Evidence Ledger", "pcag.apps.evidence_ledger.main:app", 8005),
    ("PLC Adapter",     "pcag.apps.plc_adapter.main:app",     8007),
    ("Sensor Gateway",  "pcag.apps.sensor_gateway.main:app",  8003),
    ("OT Interface",    "pcag.apps.ot_interface.main:app",    8004),
    ("Policy Admin",    "pcag.apps.policy_admin.main:app",    8006),
    ("Gateway Core",    "pcag.apps.gateway.main:app",         8000),
    ("Dashboard",       "pcag.apps.dashboard.main:app",       8008),
]

processes = []


def start_all():
    print("=" * 60)
    print("PCAG Service Launcher")
    print("=" * 60)
    
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    for name, module, port in SERVICES:
        print(f"  Starting {name} on port {port}...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", module,
             "--host", "0.0.0.0", "--port", str(port),
             "--log-level", "info"],
            cwd=PROJECT_ROOT,
            env=env
        )
        processes.append((name, proc, port))
        time.sleep(0.5)
    
    print()
    print("All services started:")
    for name, proc, port in processes:
        print(f"  [{name}] PID={proc.pid} Port={port}")
    print()
    print("NOTE: Safety Cluster(8001) runs separately in pcag-isaac env")
    print("Gateway: http://localhost:8000/docs")
    print("Dashboard: http://localhost:8008/")
    print()
    print("Press Ctrl+C to stop all services")


def stop_all():
    print("\nStopping all services...")
    for name, proc, port in processes:
        try:
            proc.terminate()
        except Exception:
            pass
    
    # Wait for all to finish
    for name, proc, port in processes:
        try:
            proc.wait(timeout=5)
            print(f"  [{name}] stopped")
        except subprocess.TimeoutExpired:
            proc.kill()
            print(f"  [{name}] killed")
        except Exception:
            print(f"  [{name}] already stopped")
    
    print("All services stopped.")


def main():
    start_all()
    
    try:
        while True:
            time.sleep(2)
            # Check if any process died unexpectedly
            for name, proc, port in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"  [WARNING] {name} exited with code {ret}")
                    # Remove from list to avoid repeated warnings
                    processes.remove((name, proc, port))
                    break  # Restart iteration since list changed
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()


if __name__ == "__main__":
    main()
