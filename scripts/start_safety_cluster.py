"""
Safety Cluster 전용 런처
========================
Isaac Sim은 별도 Worker 프로세스에서 자동으로 시작됩니다.
uvicorn과 Isaac Sim이 프로세스 레벨에서 분리되므로
asyncio/signal 충돌이 발생하지 않습니다.

실행 방법:
  conda activate pcag-isaac
  python scripts/start_safety_cluster.py
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

def main():
    print("=" * 60)
    print("PCAG Safety Cluster + Isaac Sim Worker")
    print(f"Port: 8001")
    print(f"Python: {sys.version}")
    print("=" * 60)
    
    # Isaac Sim 활성화
    os.environ["PCAG_ENABLE_ISAAC"] = "true"
    
    import uvicorn
    uvicorn.run(
        "pcag.apps.safety_cluster.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        workers=1,
        reload=False
    )

if __name__ == "__main__":
    main()
