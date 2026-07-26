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
    
    plan = relationship("Plan", back_populates="users")
    
    created_at = Column(DateTime, default=datetime.utcnow)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action_type = Column(String) # 'upload_tiktok', 'upload_youtube', 'process_video'
    date_str = Column(String) # 'YYYY-MM-DD'
    count = Column(Integer, default=1)
    
# Khởi tạo Database SQLite
DB_DIR = os.path.dirname(os.path.abspath(__file__))
engine = create_engine(f"sqlite:///{os.path.join(DB_DIR, 'saas.db')}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
