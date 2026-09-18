from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    price = Column(Float, default=0.0)
    
    max_daily_videos = Column(Integer, default=5)
    max_concurrent_processes = Column(Integer, default=1)
    can_use_ai_script = Column(Boolean, default=False)
    watermark_removal = Column(Boolean, default=False)
    
    users = relationship("User", back_populates="plan")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user") # 'admin', 'vip', 'user'
    is_active = Column(Boolean, default=True)
    
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    plan_expires_at = Column(DateTime, nullable=True)
    hwid = Column(String, nullable=True, index=True)
    
    plan = relationship("Plan", back_populates="users")
    
    created_at = Column(DateTime, default=datetime.utcnow)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action_type = Column(String) # 'upload_tiktok', 'upload_youtube', 'process_video'
    date_str = Column(String) # 'YYYY-MM-DD'
    count = Column(Integer, default=1)

class Feedback(Base):
    __tablename__ = "feedbacks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String, index=True)
    rating = Column(Integer, default=5) # 1 - 5 sao
    category = Column(String, default="Đánh giá") # 'Đánh giá', 'Góp ý tính năng', 'Báo lỗi', 'Khác'
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)
    
# Khởi tạo Database SQLite
DB_DIR = os.path.dirname(os.path.abspath(__file__))
engine = create_engine(f"sqlite:///{os.path.join(DB_DIR, 'saas.db')}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Tự động migrate các cột mới nếu bảng users đã tồn tại từ trước
    import sqlite3
    db_file = os.path.join(DB_DIR, 'saas.db')
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in cursor.fetchall()]
        if cols:
            if "hwid" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN hwid TEXT")
            if "plan_expires_at" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN plan_expires_at TIMESTAMP")
            conn.commit()
        conn.close()
    except Exception as e:
        pass
