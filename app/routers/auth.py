from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, Role
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.bruteforce import bruteforce
from app.core.logging import get_security_logger

sec_logger = get_security_logger()

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register")
def register(username: str, password: str, db: Session = Depends(get_db)):
    username = username.strip()

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username too short")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password too short")

    exists = db.scalar(select(User).where(User.username == username))
    if exists:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=Role.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/login")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    key = f"{form.username}:{ip}"

    if bruteforce.is_blocked(key):
        sec_logger.warning(f"Bruteforce blocked for user={form.username} ip={ip}")
        raise HTTPException(status_code=429, detail="Too many login attempts")

    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.password_hash):
        bruteforce.register_fail(key)
        sec_logger.warning(f"Login failed user={form.username} ip={ip}")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user.username, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    sec_logger.info(f"Login success user={user.username} ip={ip}")
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}
