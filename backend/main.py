from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import os
from pydantic import BaseModel

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
    
    free_plan = db.query(models.Plan).filter(models.Plan.name == "Free").first()
    if not free_plan:
        raise HTTPException(status_code=500, detail="Default Free plan not found in database")
        
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role,
        plan_id=free_plan.id
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
    max_videos = plan.max_daily_videos if plan else 0
    
    return {
        "username": current_user.username,
        "role": current_user.role,
        "plan_name": plan.name if plan else "Unknown",
        "max_daily_videos": max_videos,
        "can_use_ai": plan.can_use_ai_script if plan else False,
        "used_today": total_used_today,
        "remaining": max_videos - total_used_today
    }

@app.post("/track")
def track_usage(req: TrackRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Check quota first
    usage = db.query(models.UsageLog).filter(
        models.UsageLog.user_id == current_user.id,
        models.UsageLog.date_str == today_str
    ).all()
    total_used_today = sum(log.count for log in usage)
    
    if total_used_today >= (current_user.plan.max_daily_videos if current_user.plan else 0):
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

@app.post("/ai/generate")
def proxy_gemini_api(req: PromptRequest, current_user: models.User = Depends(get_current_user)):
    if not current_user.plan or not current_user.plan.can_use_ai_script:
        raise HTTPException(status_code=403, detail="Tính năng AI chỉ dành cho gói Pro và VIP. Vui lòng nâng cấp.")
        
    # Ở đây Backend sẽ dùng Key Gemini riêng (được giấu kín trên server)
    import os
    import google.generativeai as genai
    
    server_api_key = os.getenv("SERVER_GEMINI_API_KEY", "")
    if not server_api_key:
        raise HTTPException(status_code=500, detail="Server API Key not configured")
        
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

class AdminUserUpdate(BaseModel):
    password: str = None
    role: str = None
    plan_name: str = None

@app.get("/admin/users")
def get_users(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    results = []
    for u in users:
        results.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "plan_name": u.plan.name if u.plan else "Unknown",
            "created_at": str(u.created_at)
        })
    return results

@app.post("/admin/users")
def admin_create_user(user: AdminUserCreate, admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
        
    plan = db.query(models.Plan).filter(models.Plan.name == user.plan_name).first()
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan name")
        
    hashed = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed,
        role=user.role,
        plan_id=plan.id
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
