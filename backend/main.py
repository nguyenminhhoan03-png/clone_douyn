from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import os, sys
from pydantic import BaseModel

# Thêm thư mục backend vào sys.path
sys.path.insert(0, os.path.dirname(__file__))

import models, auth

models.init_db()

app = FastAPI(title="Douyin SaaS API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Dependency
def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API Models
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    max_daily_videos: int = 5
    hwid: str = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TrackRequest(BaseModel):
    action_type: str

# Helper to get current user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except auth.JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    if user.hwid:
        existing_hwid = db.query(models.User).filter(models.User.hwid == user.hwid).first()
        if existing_hwid:
            raise HTTPException(status_code=400, detail="Thiết bị này đã đăng ký tài khoản dùng thử trước đó. Mỗi máy chỉ được đăng ký 1 tài khoản!")
    
    free_plan = db.query(models.Plan).filter(models.Plan.name == "Free").first()
    if not free_plan:
        free_plan = models.Plan(name="Free", max_daily_videos=5, can_use_ai_script=True, price=0.0)
        db.add(free_plan)
        db.commit()
        db.refresh(free_plan)

    # Đọc cấu hình gói Free từ system_configs nếu có
    free_days = 10
    pkg_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "packages").first()
    if pkg_cfg and pkg_cfg.value:
        try:
            import json
            pkgs = json.loads(pkg_cfg.value)
            for p in pkgs:
                if str(p.get("code", "")).strip().upper() == "FREE":
                    free_days = int(p.get("days", 10))
                    max_v = int(p.get("max_daily_videos", 5))
                    free_plan.max_daily_videos = max_v
                    free_plan.can_use_ai_script = bool(p.get("can_use_ai", True))
                    db.commit()
                    break
        except Exception:
            pass
        
    hashed_password = auth.get_password_hash(user.password)
    expires_at = datetime.utcnow() + timedelta(days=free_days)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role,
        plan_id=free_plan.id,
        plan_expires_at=expires_at,
        hwid=user.hwid
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}


@app.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
def read_users_me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Calculate today's usage
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    usage = db.query(models.UsageLog).filter(
        models.UsageLog.user_id == current_user.id,
        models.UsageLog.date_str == today_str
    ).all()
    
    total_used_today = sum(log.count for log in usage)
    
    plan = current_user.plan
    max_videos = plan.max_daily_videos if plan else 5
    
    # Calculate expiration and is_expired
    is_expired = False
    days_left = 0
    if current_user.role == "admin":
        expire_date = "Vĩnh viễn (Admin)"
        is_expired = False
        days_left = 9999
    elif current_user.plan_expires_at:
        now = datetime.utcnow()
        if current_user.plan_expires_at < now:
            is_expired = True
            days_left = 0
        else:
            days_left = max(0, (current_user.plan_expires_at.date() - now.date()).days)
        expire_date = current_user.plan_expires_at.strftime("%d/%m/%Y")
    else:
        expire_date = "Chưa có"
        is_expired = False
        days_left = 0

    return {
        "username": current_user.username,
        "role": current_user.role,
        "plan_name": plan.name if plan else "Free",
        "max_daily_videos": max_videos,
        "can_use_ai": plan.can_use_ai_script if plan else False,
        "used_today": total_used_today,
        "remaining": max(0, max_videos - total_used_today),
        "expire_date": expire_date,
        "is_expired": is_expired,
        "days_left": days_left
    }

@app.post("/track")
def track_usage(req: TrackRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin" and current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Tài khoản dùng thử/bản quyền đã hết hạn. Vui lòng gia hạn!")

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Check quota first
    usage = db.query(models.UsageLog).filter(
        models.UsageLog.user_id == current_user.id,
        models.UsageLog.date_str == today_str
    ).all()
    total_used_today = sum(log.count for log in usage)
    
    max_videos = current_user.plan.max_daily_videos if current_user.plan else 5
    if current_user.role != "admin" and total_used_today >= max_videos:
        raise HTTPException(status_code=403, detail="Daily quota exceeded")
        
    # Update log
    log = db.query(models.UsageLog).filter(
        models.UsageLog.user_id == current_user.id,
        models.UsageLog.date_str == today_str,
        models.UsageLog.action_type == req.action_type
    ).first()
    
    if log:
        log.count += 1
    else:
        new_log = models.UsageLog(
            user_id=current_user.id,
            action_type=req.action_type,
            date_str=today_str,
            count=1
        )
        db.add(new_log)
        
    db.commit()
    return {"message": "Tracked successfully", "used_today": total_used_today + 1}

class PromptRequest(BaseModel):
    prompt: str
    api_key: str = None
    key_type: str = None  # "groq" hoặc "gemini"

@app.post("/ai/generate")
def proxy_gemini_api(req: PromptRequest, current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin" and current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Tài khoản dùng thử/bản quyền đã hết hạn. Vui lòng gia hạn!")

    if not current_user.plan or not current_user.plan.can_use_ai_script:
        raise HTTPException(status_code=403, detail="Gói cước của bạn không bao gồm API Key AI dùng chung của máy chủ. Vui lòng vào tab Cài Đặt nhập Gemini API Key miễn phí của bạn hoặc nâng cấp gói hỗ trợ sẵn AI.")
    
    import os
    
    # Nếu client gửi API Key riêng (Groq hoặc Gemini)
    if req.api_key:
        if req.key_type == "groq" or req.api_key.startswith("gsk_"):
            # Gọi Groq API (OpenAI-compatible)
            try:
                import requests as http_requests
                resp = http_requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": req.prompt}],
                        "temperature": 0.3,
                        "max_tokens": 4096
                    },
                    headers={
                        "Authorization": f"Bearer {req.api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=30
                )
                if resp.status_code == 200:
                    return {"text": resp.json()["choices"][0]["message"]["content"]}
                else:
                    raise HTTPException(status_code=resp.status_code, detail=f"Groq API Error: {resp.text}")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Groq Error: {str(e)}")
        else:
            # Gọi Gemini API với key của client
            try:
                import google.generativeai as genai
                genai.configure(api_key=req.api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(req.prompt)
                return {"text": response.text}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Gemini Error: {str(e)}")
    
    # Fallback: Dùng Server Gemini Key
    import google.generativeai as genai
    
    server_api_key = os.getenv("SERVER_GEMINI_API_KEY", "")
    if not server_api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình API Key (GROQ hoặc GEMINI)")
        
    try:
        genai.configure(api_key=server_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(req.prompt)
        return {"text": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# Admin User Management APIs
# ==============================================================================
def get_admin_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

class AdminUserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    plan_name: str = "Free"
    days_to_add: int = 30

class AdminUserUpdate(BaseModel):
    password: str = None
    role: str = None
    plan_name: str = None
    days_to_add: int = None

@app.get("/admin/users")
def get_users(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    results = []
    now = datetime.utcnow()
    for u in users:
        is_exp = False
        if u.role != "admin" and u.plan_expires_at and u.plan_expires_at < now:
            is_exp = True
        exp_str = u.plan_expires_at.strftime("%d/%m/%Y") if u.plan_expires_at else ("Vĩnh viễn" if u.role == "admin" else "Chưa có")
        created_str = u.created_at.strftime("%d/%m/%Y %H:%M") if u.created_at else "Chưa ghi nhận"
        p_name = u.plan.name if u.plan else "Free"
        max_videos = u.plan.max_daily_videos if u.plan else 5
        can_ai = u.plan.can_use_ai_script if u.plan else False
        results.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "plan_name": p_name,
            "max_daily_videos": max_videos,
            "can_use_ai_script": can_ai,
            "hwid": u.hwid or "Chưa khóa thiết bị",
            "created_at": created_str,
            "expire_date": exp_str,
            "is_expired": is_exp
        })
    return results

@app.post("/admin/users/{user_id}/reset_hwid")
def admin_reset_hwid(user_id: int, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hwid = None
    db.commit()
    return {"message": f"Đã mở khóa thiết bị (Reset HWID) thành công cho tài khoản '{user.username}'."}

@app.post("/admin/users")
def admin_create_user(user: AdminUserCreate, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
        
    plan = db.query(models.Plan).filter(models.Plan.name == user.plan_name).first()
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan name")
        
    hashed = auth.get_password_hash(user.password)
    expires_at = None
    if user.days_to_add and user.days_to_add > 0:
        expires_at = datetime.utcnow() + timedelta(days=user.days_to_add)

    db_user = models.User(
        username=user.username,
        hashed_password=hashed,
        role=user.role,
        plan_id=plan.id,
        plan_expires_at=expires_at
    )
    db.add(db_user)
    db.commit()
    return {"message": "User created successfully"}

@app.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, user: AdminUserUpdate, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.password:
        db_user.hashed_password = auth.get_password_hash(user.password)
    if user.role:
        db_user.role = user.role
    if user.plan_name:
        plan = db.query(models.Plan).filter(models.Plan.name == user.plan_name).first()
        if plan:
            db_user.plan_id = plan.id
    if user.days_to_add and user.days_to_add > 0:
        now = datetime.utcnow()
        if db_user.plan_expires_at and db_user.plan_expires_at > now:
            db_user.plan_expires_at += timedelta(days=user.days_to_add)
        else:
            db_user.plan_expires_at = now + timedelta(days=user.days_to_add)
            
    db.commit()
    return {"message": "User updated successfully"}

@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Xóa logs của user
    db.query(models.UsageLog).filter(models.UsageLog.user_id == user_id).delete()
    
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}

# ==============================================================================
# Admin Plan Management APIs
# ==============================================================================
class PlanUpdate(BaseModel):
    max_daily_videos: int = None
    can_use_ai_script: bool = None

@app.get("/admin/plans")
def get_plans(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    plans = db.query(models.Plan).all()
    results = []
    for p in plans:
        results.append({
            "id": p.id,
            "name": p.name,
            "max_daily_videos": p.max_daily_videos,
            "can_use_ai_script": p.can_use_ai_script
        })
    return results

@app.put("/admin/plans/{plan_id}")
def update_plan(plan_id: int, plan: PlanUpdate, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    db_plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.max_daily_videos is not None:
        db_plan.max_daily_videos = plan.max_daily_videos
    if plan.can_use_ai_script is not None:
        db_plan.can_use_ai_script = plan.can_use_ai_script
        
    db.commit()
    return {"message": "Plan updated successfully"}

# ==============================================================================
# Feedback & Review APIs
# ==============================================================================
class FeedbackCreate(BaseModel):
    rating: int = 5
    category: str = "Đánh giá"
    content: str

@app.post("/api/feedback")
def submit_feedback(fb: FeedbackCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not fb.content or not fb.content.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập nội dung đánh giá/góp ý.")
    
    new_fb = models.Feedback(
        user_id=current_user.id,
        username=current_user.username,
        rating=max(1, min(5, fb.rating)),
        category=fb.category or "Đánh giá",
        content=fb.content.strip(),
        created_at=datetime.utcnow()
    )
    db.add(new_fb)
    db.commit()
    return {"message": "Cảm ơn bạn đã gửi đánh giá & góp ý! Ý kiến của bạn sẽ giúp chúng tôi hoàn thiện phần mềm tốt hơn."}

@app.get("/admin/feedbacks")
def admin_get_feedbacks(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    feedbacks = db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()
    total = len(feedbacks)
    avg_rating = round(sum(f.rating for f in feedbacks) / total, 1) if total > 0 else 5.0
    
    results = []
    for f in feedbacks:
        results.append({
            "id": f.id,
            "username": f.username,
            "rating": f.rating,
            "category": f.category,
            "content": f.content,
            "created_at": f.created_at.strftime("%d/%m/%Y %H:%M") if f.created_at else ""
        })
    return {
        "total": total,
        "avg_rating": avg_rating,
        "feedbacks": results
    }

# ==============================================================================
# System Config & Payment Info APIs
# ==============================================================================
@app.get("/admin/config")
def admin_get_config(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    configs = db.query(models.SystemConfig).all()
    res = {}
    for c in configs:
        res[c.key] = c.value
    return res

@app.put("/admin/config")
def admin_save_config(data: dict, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    import json
    for k, v in data.items():
        val_str = str(v) if not isinstance(v, str) else v
        cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == k).first()
        if cfg:
            cfg.value = val_str
        else:
            cfg = models.SystemConfig(key=k, value=val_str)
            db.add(cfg)
    
    # Đồng bộ các gói vào bảng plans nếu packages được cập nhật
    if "packages" in data:
        try:
            pkgs = json.loads(data["packages"]) if isinstance(data["packages"], str) else data["packages"]
            for p in pkgs:
                p_code = str(p.get("code", "")).strip()
                p_name = str(p.get("name", "")).strip()
                p_max = int(p.get("max_daily_videos", 5))
                p_ai = bool(p.get("can_use_ai", True))
                p_price = float(p.get("price", 0))

                plan_name_target = "Free" if p_code.upper() == "FREE" else p_name
                plan = db.query(models.Plan).filter(models.Plan.name == plan_name_target).first()
                if not plan and p_code.upper() != "FREE":
                    plan = db.query(models.Plan).filter(models.Plan.name == p_code).first()
                
                if plan:
                    plan.max_daily_videos = p_max
                    plan.can_use_ai_script = p_ai
                    plan.price = p_price
                else:
                    new_p = models.Plan(
                        name=plan_name_target,
                        max_daily_videos=p_max,
                        can_use_ai_script=p_ai,
                        price=p_price
                    )
                    db.add(new_p)
        except Exception:
            pass

    db.commit()
    return {"message": "Đã lưu cấu hình thành công!"}

@app.get("/payment/info")
def get_payment_info(db: Session = Depends(get_db)):
    configs = db.query(models.SystemConfig).all()
    res = {}
    for c in configs:
        res[c.key] = c.value
        
    if "packages" in res:
        try:
            import json
            res["packages"] = json.loads(res["packages"])
        except Exception:
            pass
            
    return res


