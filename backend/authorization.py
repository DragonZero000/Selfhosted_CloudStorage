import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic_settings import BaseSettings
from pydantic import BaseModel
import db
from db import User
from argon2 import PasswordHasher, exceptions
import argon2

class Settings(BaseSettings):
    SECRET_KEY: str = "hs256"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

class UserCreate(BaseModel):
    login: str
    password: str

settings = Settings()

ph = PasswordHasher(
    time_cost=2,
    memory_cost=102400,     # 100 MiB
    parallelism=8,
    hash_len=32,
    salt_len=16,
    encoding='utf-8',
    type=argon2.Type.ID,    # Argon2id
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
    db.insert_user_data(user.login, hashed_password)
    return True

# JWT функции
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

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

# FastAPI приложение
app = FastAPI()
ori = ["http://localhost:54718", "http://127.0.0.1:54718"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # Разрешает запросы с этих адресов
    allow_credentials=False,           # Разрешает передачу cookies и заголовков авторизации
    allow_methods=["*"],              # Разрешает все методы (GET, POST, OPTIONS и т.д.)
    allow_headers=["*"],              # Разрешает все заголовки
)
@app.post("/register")
def register(user: UserCreate):
    db_user = db.get_user_data(user.login)
    if db_user:
        raise HTTPException(status_code=400, detail="Login already registered")
    new_user = create_user(user)
    if not new_user:
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
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.login}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# Запуск: uvicorn app:app --reload