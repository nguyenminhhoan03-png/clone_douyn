from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
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
    details: str = None
    username: str = None
    hwid: str = None

class UninstallRequest(BaseModel):
    action_type: str = "UNINSTALL"
    username: str = None
    hwid: str = None
    details: str = None
    reason: str = None
    app_version: str = None

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
        # 1. Kiểm tra nếu HWID nằm trong Blacklist (bị Admin chặn)
        bl_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "blacklisted_hwids").first()
        if bl_cfg and bl_cfg.value:
            try:
                import json
                bl_list = json.loads(bl_cfg.value)
                if isinstance(bl_list, list) and user.hwid in bl_list:
                    raise HTTPException(status_code=403, detail="Thiết bị này đã bị khóa/chặn tạo tài khoản bởi Quản trị viên!")
            except HTTPException:
                raise
            except Exception:
                pass

        # 2. Kiểm tra nếu bật chống trùng thiết bị khi đăng ký Free
        enforce_hwid = True
        hw_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enforce_hwid_register").first()
        if hw_cfg and str(hw_cfg.value).strip().lower() == "false":
            enforce_hwid = False

        if enforce_hwid:
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
        # Nếu user chưa có ngày hết hạn: đọc số ngày dùng thử gói Free từ cấu hình Admin cài đặt
        free_days = 10
        pkg_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "packages").first()
        if pkg_cfg and pkg_cfg.value:
            try:
                import json
                pkgs = json.loads(pkg_cfg.value)
                for p in pkgs:
                    if str(p.get("code", "")).strip().upper() == "FREE":
                        free_days = int(p.get("days", 10))
                        break
            except Exception:
                pass

        now = datetime.utcnow()
        current_user.plan_expires_at = now + timedelta(days=free_days)
        db.commit()
        expire_date = current_user.plan_expires_at.strftime("%d/%m/%Y")
        is_expired = False
        days_left = free_days

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
    
    # Ghi nhận Telemetry Log hệ thống
    try:
        t_log = models.TelemetryLog(
            username=admin.username,
            action="RESET_HWID",
            details=f"Admin '{admin.username}' đã mở khóa thiết bị (Reset HWID) thành công cho tài khoản '{user.username}'",
            ip_address=None
        )
        db.add(t_log)
    except Exception:
        pass
        
    db.commit()
    return {"message": f"Đã mở khóa thiết bị (Reset HWID) thành công cho tài khoản '{user.username}'."}

# ==============================================================================
# Admin Device / HWID Management APIs
# ==============================================================================
class DeviceAction(BaseModel):
    hwid: str
    user_id: int = None

@app.get("/admin/devices")
def admin_get_devices(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    import json
    # Lấy danh sách blacklist
    bl_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "blacklisted_hwids").first()
    bl_list = []
    if bl_cfg and bl_cfg.value:
        try:
            bl_list = json.loads(bl_cfg.value)
            if not isinstance(bl_list, list): bl_list = []
        except Exception:
            bl_list = []

    # Lấy danh sách users có gán HWID
    users_with_hwid = db.query(models.User).filter(models.User.hwid.isnot(None), models.User.hwid != "").all()
    devices = []
    seen_hwids = set()

    for u in users_with_hwid:
        hw = str(u.hwid).strip()
        if not hw: continue
        seen_hwids.add(hw)
        is_blocked = hw in bl_list
        devices.append({
            "hwid": hw,
            "username": u.username,
            "user_id": u.id,
            "role": u.role,
            "plan_name": u.plan.name if u.plan else "Free",
            "created_at": u.created_at.strftime("%d/%m/%Y %H:%M") if u.created_at else "",
            "is_blocked": is_blocked,
            "status": "blocked" if is_blocked else "active"
        })

    # Thêm các HWID trong blacklist nhưng chưa hoặc không còn gán vào user nào
    for hw in bl_list:
        if hw and hw not in seen_hwids:
            devices.append({
                "hwid": hw,
                "username": "(Không có user)",
                "user_id": None,
                "role": "",
                "plan_name": "-",
                "created_at": "-",
                "is_blocked": True,
                "status": "blocked"
            })

    return {
        "total": len(devices),
        "blacklisted_count": len(bl_list),
        "devices": devices
    }

@app.post("/admin/devices/unlock")
def admin_unlock_device(req: DeviceAction, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    hwid = req.hwid.strip()
    if not hwid:
        raise HTTPException(status_code=400, detail="Mã HWID không hợp lệ")

    # 1. Gỡ HWID khỏi tất cả user đang gán mã này
    users = db.query(models.User).filter(models.User.hwid == hwid).all()
    cleared_names = []
    for u in users:
        u.hwid = None
        cleared_names.append(u.username)

    # 2. Gỡ khỏi blacklist nếu có
    import json
    bl_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "blacklisted_hwids").first()
    if bl_cfg and bl_cfg.value:
        try:
            bl_list = json.loads(bl_cfg.value)
            if hwid in bl_list:
                bl_list.remove(hwid)
                bl_cfg.value = json.dumps(bl_list)
        except Exception:
            pass

    # Ghi nhận Telemetry Log
    try:
        details = f"Admin '{admin.username}' đã gỡ khóa thiết bị [{hwid[:12]}...]"
        if cleared_names:
            details += f" (tài khoản: {', '.join(cleared_names)})"
        t_log = models.TelemetryLog(username=admin.username, action="RESET_HWID", details=details)
        db.add(t_log)
    except Exception:
        pass

    db.commit()
    return {"message": "Đã gỡ khóa thiết bị thành công! Máy này có thể đăng ký tài khoản mới ngay."}

@app.post("/admin/devices/toggle_block")
def admin_toggle_block_device(req: DeviceAction, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    import json
    hwid = req.hwid.strip()
    if not hwid:
        raise HTTPException(status_code=400, detail="Mã HWID không hợp lệ")

    bl_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "blacklisted_hwids").first()
    bl_list = []
    if bl_cfg and bl_cfg.value:
        try:
            bl_list = json.loads(bl_cfg.value)
            if not isinstance(bl_list, list): bl_list = []
        except Exception:
            bl_list = []
    else:
        if not bl_cfg:
            bl_cfg = models.SystemConfig(key="blacklisted_hwids", value="[]")
            db.add(bl_cfg)

    is_blocked = False
    if hwid in bl_list:
        bl_list.remove(hwid)
        action_msg = "Đã bỏ chặn thiết bị."
        is_blocked = False
    else:
        bl_list.append(hwid)
        action_msg = "Đã khóa/chặn thiết bị vào Blacklist thành công!"
        is_blocked = True

    bl_cfg.value = json.dumps(bl_list)

    # Ghi nhận Telemetry Log
    try:
        t_log = models.TelemetryLog(
            username=admin.username,
            action="BLOCK_DEVICE" if is_blocked else "UNBLOCK_DEVICE",
            details=f"Admin '{admin.username}' {'đã chặn thiết bị' if is_blocked else 'đã bỏ chặn thiết bị'} [{hwid[:12]}...]"
        )
        db.add(t_log)
    except Exception:
        pass

    db.commit()
    return {"message": action_msg, "is_blocked": is_blocked}

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

# ==============================================================================
# Douyin Cookie Auto-Sync API (Dành cho Client tự động đồng bộ Cookie)
# ==============================================================================
DEFAULT_DOUYIN_COOKIE = """# Netscape HTTP Cookie File
# This file is generated by yt-dlp.  Do not edit.

.douyin.com\tTRUE\t/\tFALSE\t1819008440\tUIFID\t4f370c6d8fb718a382d31de50859ac71a63e1a5cc19a7a2de24e63803f467b410d09fd2003106cba53f2ff73f64f52a2d8a8c135baa9319f7be697a184ed5c7dfd5e0d8fd7d12588714929efdef68d993691e994e3db028114cc40c77644bc741f25b90bfcfec86514c42b36a329f92208066bd202a359afe337676de41c79f377ee2c10c1b0cd6102917f185008e617987bff812508052af0abc3136a30ff9d
.douyin.com\tTRUE\t/\tTRUE\t1815553881\tsid_guard\t1504328916ddf757c53c1b6e53839ed5%7C1784475079%7C5184000%7CThu%2C+17-Sep-2026+15%3A31%3A19+GMT
.douyin.com\tTRUE\t/\tTRUE\t1815644443\tttwid\t1%7C9AifIXZrTrLqXWUGqrLHSPONvX9Ihn8RLgqbZdjuyGY%7C1784564803%7C6f187b59a12ecaf7b77a801a980d838ec01e838d9f393110578485048858ffc2
.douyin.com\tTRUE\t/\tFALSE\t1819100443\tenter_pc_once\t1
.douyin.com\tTRUE\t/\tFALSE\t1819009881\tpassport_assist_user\tCkT9uIHFGjTZTznT3N9QE4aG7P9jyqnfQZHTlz1cUQ2Qsg4WpTyhlkbWifnm_rgVH0HBgHrwS2yQ26Hqe2wX-QbcPE3dLBpKCjwAAAAAAAAAAAAAUK0BuCwtgnAHPaSDFU11ZpJgafJdb8Ne8Mjr9lsBQQxX38U3D3_rvO0i6ZrJqMKwbpsQvqCXDhiJr9ZUIAEiAQN7lEKv
.douyin.com\tTRUE\t/\tFALSE\t1817785750\tUIFID_TEMP\t4f370c6d8fb718a382d31de50859ac71a63e1a5cc19a7a2de24e63803f467b411722faf7952e1d276e5e027d3ce7d182f3769f7166c9d265fdc2779e152a3b893f22b5e058a7ebb94718fa8bff2daed5
.douyin.com\tTRUE\t/\tFALSE\t1816077485\todin_tt\t115581ef1147130bc1157d000ca39e3458991bae7671d3ad939239e8b614b9885ee6d98e690f2f22673657a4c46cc1da258914c41a3bbf753e8b3ac6a6873c7c9ad9d4b94ffbf6657c6daaeb14fc197d
.douyin.com\tTRUE\t/\tTRUE\t1819677709\ts_v_web_id\tverify_1a0c07f0c09_cci1XhXo9wfrGTseVzTGiwyRe0aPfXD2
www.douyin.com\tFALSE\t/\tFALSE\t1817785761\tfpk1\tU2FsdGVkX19CCdR4j1MCwYBii/DX76ynG71viywWGJTj9XIBvUF3S4cjENZEkaaOaaGblV063INcnSQHvBDtaQ==
www.douyin.com\tFALSE\t/\tFALSE\t1816075596\t__ac_signature\t_02B4Z6wo00f01gjeJMwAAIDDxs6y30xIP3oI.iBAAOh414
www.douyin.com\tFALSE\t/\tFALSE\t1817785761\tfpk2\t16fee37559dbd42b448204446d02089f
v3-dy-o.zjcdn.com\tFALSE\t/\tFALSE\t0\tsid_tt\t1504328916ddf757c53c1b6e53839ed5
api-play.amemv.com\tFALSE\t/\tFALSE\t0\tsid_tt\t1504328916ddf757c53c1b6e53839ed5
api.amemv.com\tFALSE\t/\tFALSE\t0\tsid_tt\t1504328916ddf757c53c1b6e53839ed5
api-play-hl.amemv.com\tFALSE\t/\tFALSE\t0\tsid_tt\t1504328916ddf757c53c1b6e53839ed5
api-hl.amemv.com\tFALSE\t/\tFALSE\t0\tsid_tt\t1504328916ddf757c53c1b6e53839ed5
.iesdouyin.com\tTRUE\t/\tFALSE\t1816626222\tttwid\t1%7CsvcgaM5WGFqg4S6NZKC4_EJHPuTxfG-WkoDCTwPkx9E%7C1784772451%7Cd549e40bd8afa2d05443efb3cf0fe9c01ba042dc7f5117a9a0d00478588b4350
"""

@app.get("/api/system/douyin-cookie")
@app.get("/system/douyin-cookie")
def get_system_douyin_cookie(db: Session = Depends(get_db)):
    """Trả về cookie Douyin mới nhất để Client tự động tải về ghi vào máy."""
    # 1. Ưu tiên lấy từ SystemConfig trong Database (nếu Admin đã cập nhật)
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "douyin_cookie").first()
    if cfg and cfg.value and len(cfg.value.strip()) > 20:
        return {"cookie": cfg.value.strip()}

    # 2. Đọc từ file vật lý trên server nếu có
    from pathlib import Path
    candidate_paths = [
        Path(__file__).resolve().parent.parent / "config" / "cookies" / "douyin_cookies.txt",
        Path("/app/config/cookies/douyin_cookies.txt"),
        Path.cwd() / "config" / "cookies" / "douyin_cookies.txt",
    ]
    for p in candidate_paths:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore").strip()
                if len(content) > 20:
                    return {"cookie": content}
            except Exception:
                pass

    # 3. Fallback cookie mặc định tích hợp sẵn (đảm bảo luôn trả về cookie hợp lệ)
    return {"cookie": DEFAULT_DOUYIN_COOKIE.strip()}

@app.post("/admin/douyin-cookie")
def admin_set_douyin_cookie(data: dict, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    cookie_str = data.get("cookie", "").strip()
    if not cookie_str:
        raise HTTPException(status_code=400, detail="Cookie content is empty")
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "douyin_cookie").first()
    if cfg:
        cfg.value = cookie_str
    else:
        cfg = models.SystemConfig(key="douyin_cookie", value=cookie_str)
        db.add(cfg)
    db.commit()
    return {"message": "Đã cập nhật Douyin cookie thành công!"}

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

# ==============================================================================
# SePay Webhook Auto-Payment Activation APIs
# ==============================================================================
@app.get("/webhook/sepay")
@app.get("/api/webhook/sepay")
def sepay_webhook_status():
    return {
        "status": "ready",
        "gateway": "SePay VietQR Webhook Listener",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }

@app.post("/webhook/sepay")
@app.post("/api/webhook/sepay")
async def sepay_webhook_handler(request: Request, db: Session = Depends(get_db)):
    """
    Xử lý Webhook tự động từ SePay (https://sepay.vn).
    Tự động đối soát nội dung chuyển khoản, kích hoạt hoặc gia hạn VIP ngay lập tức.
    """
    try:
        data = await request.json()
    except Exception:
        return {"success": False, "message": "Invalid JSON body"}

    import json, re

    # 1. Xác thực Webhook Token (nếu cấu hình)
    cfg_token = db.query(models.SystemConfig).filter(models.SystemConfig.key == "webhook_token").first()
    if cfg_token and cfg_token.value and cfg_token.value.strip():
        secret_token = cfg_token.value.strip()
        auth_header = request.headers.get("Authorization", "")
        key_header = request.headers.get("x-sepay-api-key", "")
        param_token = request.query_params.get("token", "")
        # Nếu có gửi token xác thực thì phải khớp
        if auth_header or key_header or param_token:
            if secret_token not in auth_header and key_header != secret_token and param_token != secret_token:
                raise HTTPException(status_code=401, detail="Unauthorized SePay Token")

    # 2. Kiểm tra loại giao dịch
    transfer_type = str(data.get("transferType", "in")).lower()
    if transfer_type == "out":
        return {"success": True, "message": "Ignored outgoing transaction"}

    content = str(data.get("content", "") or data.get("description", "")).strip()
    try:
        amount = float(data.get("transferAmount", 0))
    except Exception:
        amount = 0.0

    sepay_id = str(data.get("id") or "")
    ref_code = str(data.get("referenceCode") or sepay_id)

    # 3. Chống cộng trùng giao dịch (Idempotency)
    if ref_code:
        existing_log = db.query(models.TelemetryLog).filter(
            models.TelemetryLog.action == "PAYMENT_SUCCESS",
            models.TelemetryLog.details.like(f"%REF:{ref_code}%")
        ).first()
        if existing_log:
            return {"success": True, "message": f"Transaction {ref_code} already processed previously"}

    # 4. Lấy tiền tố và danh sách gói cước từ cấu hình
    prefix_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "payment_prefix").first()
    payment_prefix = prefix_cfg.value.strip().upper() if (prefix_cfg and prefix_cfg.value) else "TOOLVIP"

    pkgs_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "packages").first()
    packages = []
    if pkgs_cfg and pkgs_cfg.value:
        try:
            packages = json.loads(pkgs_cfg.value) if isinstance(pkgs_cfg.value, str) else pkgs_cfg.value
        except Exception:
            packages = []

    # 5. Đối soát tài khoản từ nội dung chuyển khoản
    # Cú pháp mẫu: "{prefix} {username} {package_code}" (VD: "TOOLVIP EQR 1M")
    content_upper = content.upper()
    words = re.findall(r'[A-Za-z0-9_]+', content_upper)
    all_users = db.query(models.User).all()
    target_user = None

    # Ưu tiên 1: Từ đứng ngay sau tiền tố (VD: TOOLVIP EQR -> EQR)
    if payment_prefix in words:
        p_idx = words.index(payment_prefix)
        if p_idx + 1 < len(words):
            cand = words[p_idx + 1].lower()
            for u in all_users:
                if u.username.lower() == cand:
                    target_user = u
                    break

    # Ưu tiên 2: Khớp từ nguyên vẹn với username trong database (sắp xếp độ dài giảm dần)
    if not target_user:
        matched_cands = []
        for u in all_users:
            if u.username.upper() in words:
                matched_cands.append(u)
        if matched_cands:
            matched_cands.sort(key=lambda x: len(x.username), reverse=True)
            target_user = matched_cands[0]

    # Ưu tiên 3: Tìm chuỗi con (nếu tên nick >= 3 ký tự)
    if not target_user:
        for u in sorted(all_users, key=lambda x: len(x.username), reverse=True):
            if len(u.username) >= 3 and u.username.upper() in content_upper:
                target_user = u
                break

    if not target_user:
        unresolved_log = models.TelemetryLog(
            username="sepay_webhook",
            action="PAYMENT_UNRESOLVED",
            details=f"Nhận {amount:,.0f}đ nhưng không tìm thấy username trong: '{content}'. REF:{ref_code}",
            ip_address=request.client.host if request.client else None
        )
        db.add(unresolved_log)
        db.commit()
        return {
            "success": True,
            "message": f"Payment {amount:,.0f}đ received, but no username matched in content '{content}'"
        }

    # 6. Xác định gói VIP và số ngày cộng thêm
    matched_pkg = None
    # Cách 1: Khớp mã gói (code) trong nội dung
    for p in packages:
        p_code = str(p.get("code", "")).strip().upper()
        if p_code and p_code != "FREE" and p_code in words:
            matched_pkg = p
            break

    # Cách 2: Khớp theo số tiền chuyển (price)
    if not matched_pkg and amount > 0:
        for p in packages:
            p_price = float(p.get("price", 0))
            if p_price > 0 and abs(amount - p_price) < 1.0:
                matched_pkg = p
                break

    # Cách 3: Chọn gói cao nhất có giá <= số tiền nhận được
    if not matched_pkg and amount > 0:
        valid_pkgs = [p for p in packages if float(p.get("price", 0)) > 0 and float(p.get("price", 0)) <= amount]
        if valid_pkgs:
            valid_pkgs.sort(key=lambda p: float(p.get("price", 0)), reverse=True)
            matched_pkg = valid_pkgs[0]

    if matched_pkg:
        days_to_add = int(matched_pkg.get("days", 30))
        max_daily = int(matched_pkg.get("max_daily_videos", 50))
        can_ai = bool(matched_pkg.get("can_use_ai", True))
        pkg_name = matched_pkg.get("name") or matched_pkg.get("code", "VIP")
    else:
        days_to_add = 30
        max_daily = 50
        can_ai = True
        pkg_name = "Gói VIP (30 Ngày)"

    # 7. Cập nhật hoặc tạo Plan tương ứng
    plan = db.query(models.Plan).filter(models.Plan.name == pkg_name).first()
    if not plan:
        plan = db.query(models.Plan).filter(models.Plan.name == "VIP").first()
    if not plan:
        plan = models.Plan(
            name=pkg_name,
            max_daily_videos=max_daily,
            can_use_ai_script=can_ai,
            price=amount
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

    # 8. Gia hạn thời gian sử dụng tài khoản
    now_dt = datetime.utcnow()
    current_exp = target_user.plan_expires_at
    if current_exp and current_exp > now_dt:
        target_user.plan_expires_at = current_exp + timedelta(days=days_to_add)
    else:
        target_user.plan_expires_at = now_dt + timedelta(days=days_to_add)

    target_user.plan_id = plan.id
    if target_user.role not in ("admin", "super_admin"):
        target_user.role = "vip"

    # 9. Ghi nhận Telemetry Log
    succ_log = models.TelemetryLog(
        username=target_user.username,
        action="PAYMENT_SUCCESS",
        details=f"⚡ SePay Auto: Kích hoạt thành công gói '{pkg_name}' (+{days_to_add} ngày) với số tiền {amount:,.0f}đ. Hạn mới: {target_user.plan_expires_at.strftime('%d/%m/%Y')}. REF:{ref_code}",
        ip_address=request.client.host if request.client else None
    )
    db.add(succ_log)
    db.commit()

    return {
        "success": True,
        "message": f"Kích hoạt thành công gói '{pkg_name}' (+{days_to_add} ngày) cho người dùng '{target_user.username}'",
        "username": target_user.username,
        "days_added": days_to_add,
        "new_expire": target_user.plan_expires_at.strftime("%d/%m/%Y %H:%M:%S")
    }

# ==============================================================================
# Telemetry & Admin Activity Logs APIs
# ==============================================================================
@app.post("/api/telemetry")
def log_telemetry(req: TrackRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

    uname = req.username or "Guest"
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            if payload.get("sub"):
                uname = payload.get("sub")
        except Exception:
            pass

    details_val = req.details or ""
    if req.hwid and "HWID:" not in details_val:
        details_val = f"HWID: {req.hwid} | {details_val}" if details_val else f"HWID: {req.hwid}"
        
    log = models.TelemetryLog(
        username=uname,
        action=req.action_type,
        details=details_val,
        ip_address=client_ip
    )
    db.add(log)
    db.commit()
    return {"status": "ok"}

@app.post("/api/telemetry/uninstall")
def log_uninstall(req: UninstallRequest, request: Request, db: Session = Depends(get_db)):
    """Ghi nhận sự kiện gỡ cài đặt (UNINSTALL) từ trình gỡ cài đặt Windows (Inno Setup / Uninstaller)."""
    client_ip = request.client.host if request.client else None
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

    uname = req.username or "Anonymous"
    # Nếu chưa có username cụ thể, tự động map từ HWID qua CSDL Devices
    if req.hwid and uname in ("Anonymous", "Client", "Guest", "SavedSession", ""):
        try:
            device = db.query(models.Device).filter(models.Device.hwid == req.hwid).first()
            if device and device.user:
                uname = device.user.username
        except Exception:
            pass

    info_parts = []
    if req.hwid:
        info_parts.append(f"Mã máy (HWID): {req.hwid}")
    if req.reason:
        info_parts.append(f"Lý do gỡ: {req.reason}")
    if req.app_version:
        info_parts.append(f"Bản: v{req.app_version}")
    if req.details:
        info_parts.append(req.details)

    log = models.TelemetryLog(
        username=uname,
        action="UNINSTALL",
        details=" | ".join(info_parts) if info_parts else "Người dùng đã gỡ cài đặt app qua Windows Uninstaller",
        ip_address=client_ip
    )
    db.add(log)
    db.commit()
    return {"status": "ok", "message": "Uninstall recorded successfully"}

@app.get("/api/admin/logs")
def get_admin_logs(limit: int = 100, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    logs = db.query(models.TelemetryLog).order_by(models.TelemetryLog.id.desc()).limit(limit).all()
    res = []
    for l in logs:
        time_str = l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else ""
        res.append({
            "id": l.id,
            "username": l.username,
            "action": l.action,
            "details": l.details,
            "ip_address": l.ip_address,
            "time": time_str
        })
    return res

@app.get("/admin/logs_view", response_class=HTMLResponse)
def view_admin_logs_html(token: str, db: Session = Depends(get_db)):
    # Xác thực token admin
    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges required")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    logs = db.query(models.TelemetryLog).order_by(models.TelemetryLog.id.desc()).limit(200).all()
    rows_html = ""
    for l in logs:
        time_str = l.created_at.strftime("%H:%M:%S %d/%m/%Y") if l.created_at else ""
        act = (l.action or "INFO").upper()
        act_color = "#89b4fa"
        if act == "UPLOAD": act_color = "#a6e3a1"
        elif act in ("PROCESS", "CRAWL"): act_color = "#f9e2af"
        elif act == "LOGIN": act_color = "#cba6f7"
        elif act == "RESET_HWID": act_color = "#38bdf8"
        elif act == "UNINSTALL": act_color = "#f87171"
        elif "ERROR" in act: act_color = "#f38ba8"

        rows_html += f"""
        <tr>
            <td style="color: #9399b2; font-size: 0.9em;">{time_str}</td>
            <td style="font-weight: bold; color: #cdd6f4;">{l.username}</td>
            <td><span class="badge" style="background: {act_color}; color: #11111b;">{act}</span></td>
            <td>{l.details or ''}</td>
            <td style="color: #6c7086; font-family: monospace;">{l.ip_address or '-'}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>User Activity Logs</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 20px; }}
            h1 {{ color: #89b4fa; }}
            table {{ border-collapse: collapse; width: 100%; background: #181825; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border-radius: 8px; overflow: hidden; }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #313244; }}
            th {{ background-color: #313244; color: #a6adc8; font-weight: 600; text-transform: uppercase; font-size: 0.85em; }}
            tr:hover {{ background-color: #2a2b3c; }}
            .badge {{ padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }}
        </style>
        <meta http-equiv="refresh" content="30">
    </head>
    <body>
        <h1>🔥 Live Activity Monitor</h1>
        <p>Auto-refresh every 30 seconds. Showing last 200 actions.</p>
        <table>
            <tr><th>Time</th><th>User</th><th>Action</th><th>Details</th><th>IP Address</th></tr>
            {rows_html}
        </table>
    </body>
    </html>
    """


