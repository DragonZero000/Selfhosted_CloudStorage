from datetime import datetime, timedelta, timezone
from typing import Optional

import argon2
import db
from argon2 import PasswordHasher, exceptions
from db import User
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY:                  str   = "hs256"
    ALGORITHM:                   str   = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int   = 30
    # Лимит хранилища по умолчанию для новых пользователей (в байтах).
    # 0 = загрузка заблокирована до ручного назначения лимита администратором.
    # Задаётся через переменную окружения DEFAULT_STORAGE_BYTES в .env
    DEFAULT_STORAGE_BYTES:       float = 0


class UserCreate(BaseModel):
    login: str
    password: str


settings = Settings()

ph = PasswordHasher(
    time_cost=2,
    memory_cost=102400,
    parallelism=8,
    hash_len=32,
    salt_len=16,
    encoding="utf-8",
    type=argon2.Type.ID,
)


def get_password_hash(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except exceptions.VerifyMismatchError:
        return False
    except exceptions.InvalidHashError:
        return False


def create_user(user: UserCreate):
    hashed_password = get_password_hash(user.password)
    # Новый пользователь получает лимит из настроек (по умолчанию 0 = заблокировано)
    db.insert_user_data(
        user.login,
        hashed_password,
        size_of_memory=settings.DEFAULT_STORAGE_BYTES,
    )
    return True


# ─── JWT ──────────────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.get_user_data(username)
    if user is None:
        raise credentials_exception
    return user


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/register")
def register(user: UserCreate):
    db_user = db.get_user_data(user.login)
    if db_user:
        raise HTTPException(status_code=400, detail="Login already registered")
    if not create_user(user):
        raise HTTPException(status_code=400, detail="Failed to create user")
    return {"msg": "User created"}


@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_data(form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect login or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.login},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user