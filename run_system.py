import subprocess
import time
import os
import sys

def start_backend():
    print("🚀 Starting APAS Backend (FastAPI)...")
    # 使用 python -m 确保导入路径正确
    return subprocess.Popen([sys.executable, "-m", "apps.backend.main"], cwd=os.getcwd())

def start_frontend():
    print("🎨 Starting APAS Frontend (Vite)...")
    # 假设已经在 apps/frontend 运行过 npm install
    return subprocess.Popen(["npm", "run", "dev"], cwd=os.path.join(os.getcwd(), "apps", "frontend"), shell=True)

if __name__ == "__main__":
    be_proc = None
    fe_proc = None
    try:
        be_proc = start_backend()
        time.sleep(2) # 等待后端启动
        fe_proc = start_frontend()
        
        print("\n✅ APAS System is initializing...")
        print("🔗 Frontend: http://localhost:5173")
        print("🔗 Backend:  http://localhost:8080")
        print("\nPress Ctrl+C to stop all services.")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping APAS system...")
        if be_proc: be_proc.terminate()
        if fe_proc: fe_proc.terminate()
