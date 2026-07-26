import os
import uvicorn

if __name__ == "__main__":
    print("🚀 Khởi động SaaS Backend API trên cổng 8000...")
    # Thêm đường dẫn backend vào sys.path để python nhận diện
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
    
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
