import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models import init_db, SessionLocal, User, Plan
from backend.auth import get_password_hash

def main():
    print("Khởi tạo Database...")
    init_db()
    
    db = SessionLocal()
    
    print("Tạo các gói cước (Plans)...")
    plans = {
        "Free": {"max_daily_videos": 5, "can_use_ai_script": False},
        "Pro": {"max_daily_videos": 50, "can_use_ai_script": True},
        "VIP": {"max_daily_videos": 9999, "can_use_ai_script": True}
    }
    
    db_plans = {}
    for name, config in plans.items():
        plan = db.query(Plan).filter(Plan.name == name).first()
        if not plan:
            plan = Plan(
                name=name,
                max_daily_videos=config["max_daily_videos"],
                can_use_ai_script=config["can_use_ai_script"]
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
        db_plans[name] = plan

    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        print("Tạo tài khoản admin mặc định...")
        new_admin = User(
            username="admin",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            plan_id=db_plans["VIP"].id
        )
        db.add(new_admin)
    else:
        # Update existing admin unconditionally
        admin.plan_id = db_plans["VIP"].id
        admin.role = "admin"
        db.commit()
        
    test_user = db.query(User).filter(User.username == "test_user").first()
    if not test_user:
        print("Tạo tài khoản test_user (gói Free)...")
        new_test = User(
            username="test_user",
            hashed_password=get_password_hash("123456"),
            role="user",
            plan_id=db_plans["Free"].id
        )
        db.add(new_test)
    else:
        # Update existing test_user
        if test_user.plan_id is None:
            test_user.plan_id = db_plans["Free"].id
        
    db.commit()
    db.close()
    print("Hoàn tất!")

if __name__ == "__main__":
    main()
