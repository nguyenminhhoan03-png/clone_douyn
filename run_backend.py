import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()
API_PORT = int(os.getenv("API_PORT", 8000))

if __name__ == "__main__":
    print(f"🚀 Khởi động SaaS Backend API trên cổng {API_PORT}...")
    # Thêm đường dẫn backend vào sys.path để python nhận diện
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
    
    uvicorn.run("backend.main:app", host="0.0.0.0", port=API_PORT, reload=True)
