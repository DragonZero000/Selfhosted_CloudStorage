import argon2
from argon2 import PasswordHasher
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pass@localhost:5432/appdb")

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    login          = Column(String, unique=True, nullable=False, index=True)
    password_hash  = Column(String, nullable=False)
    created_at     = Column(DateTime, default=datetime.now)
    storage_used   = Column(Float, nullable=False, default=0)
    size_of_memory = Column(Float, nullable=False, default=0)  # 0 = загрузка заблокирована
    files          = relationship("File", back_populates="user", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name   = Column(String, nullable=False)
    s3_key      = Column(String, nullable=False, unique=True)
    file_size   = Column(Float, nullable=False, default=0)
    uploaded_at = Column(DateTime, default=datetime.now)
    user        = relationship("User", back_populates="files")


Base.metadata.create_all(bind=engine)


# ─── Password hashing ─────────────────────────────────────────────────────────

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


# ─── User CRUD ────────────────────────────────────────────────────────────────

def get_user_data(login: str):
    session = SessionLocal()
    try:
        return session.query(User).filter_by(login=login).first()
    finally:
        session.close()


def get_users_data():
    session = SessionLocal()
    try:
        return session.query(User).all()
    finally:
        session.close()


def insert_user_data(login: str, password_hash: str, size_of_memory: float = 0):
    """
    Создаёт пользователя.
    size_of_memory — лимит хранилища в байтах.
    0 = загрузка заблокирована (по умолчанию для новых пользователей).
    """
    session = SessionLocal()
    try:
        session.add(User(
            login=login,
            password_hash=password_hash,
            created_at=datetime.now(),
            storage_used=0,
            size_of_memory=size_of_memory,
        ))
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def delete_user_data(login: str):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(login=login).first()
        if not user:
            print("User not found")
            return
        confirmation = input("Delete this user? (y/N): ").strip().lower() or "n"
        if confirmation == "y":
            session.delete(user)
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()


def update_user_storage(user_id: int, delta: float):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.storage_used = max(0, (user.storage_used or 0) + delta)
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def update_user_by_login(login: str, **kwargs):
    """
    Обновляет поля пользователя по логину.
    Защищённые поля (нельзя менять): id, storage_used, files.
    """
    protected = {"id", "storage_used", "files"}
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(login=login).first()
        if not user:
            print(f"User '{login}' not found")
            return False
        for key, value in kwargs.items():
            if key not in protected and hasattr(user, key):
                setattr(user, key, value)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error updating user: {e}")
        return False
    finally:
        session.close()


# ─── File CRUD ────────────────────────────────────────────────────────────────

def get_user_files(user_id: int):
    session = SessionLocal()
    try:
        return session.query(File).filter_by(user_id=user_id).order_by(File.uploaded_at.desc()).all()
    finally:
        session.close()


def get_file(file_id: int, user_id: int):
    session = SessionLocal()
    try:
        return session.query(File).filter_by(id=file_id, user_id=user_id).first()
    finally:
        session.close()


def insert_file(user_id: int, file_name: str, s3_key: str, file_size: float = 0):
    session = SessionLocal()
    try:
        f = File(user_id=user_id, file_name=file_name, s3_key=s3_key, file_size=file_size)
        session.add(f)
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.storage_used = (user.storage_used or 0) + file_size
        session.commit()
        session.refresh(f)
        return f
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def delete_file_record(file_id: int, user_id: int) -> bool:
    session = SessionLocal()
    try:
        f = session.query(File).filter_by(id=file_id, user_id=user_id).first()
        if not f:
            return False
        file_size = f.file_size
        session.delete(f)
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.storage_used = max(0, (user.storage_used or 0) - file_size)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _fmt(b):
    if b <= 0:          return "заблокировано"
    if b >= 1024 ** 3:  return f"{b / 1024 ** 3:.2f} GB"
    if b >= 1024 ** 2:  return f"{b / 1024 ** 2:.1f} MB"
    if b >= 1024:       return f"{b / 1024:.1f} KB"
    return f"{b} B"


if __name__ == "__main__":
    print("Commands: get_user | get_users | add_user | del_user | set_limit | exit")
    while True:
        command = input("> ").strip()
        if command == "exit":
            break
        elif command == "get_user":
            login = input("Login: ")
            u = get_user_data(login)
            if u:
                print(f"[{u.id}] {u.login}  used={_fmt(u.storage_used)}  limit={_fmt(u.size_of_memory)}  created={u.created_at}")
            else:
                print("Not found")
        elif command == "get_users":
            for u in get_users_data():
                print(f"[{u.id}] {u.login}  used={_fmt(u.storage_used)}  limit={_fmt(u.size_of_memory)}")
        elif command == "add_user":
            login    = input("Login: ")
            password = input("Password: ")
            mem_inp  = input("Storage limit in bytes (0 = blocked): ").strip()
            size     = float(mem_inp) if mem_inp.lstrip("-").isdigit() else 0
            insert_user_data(login, get_password_hash(password), size)
            print("Done")
        elif command == "del_user":
            login = input("Login: ")
            delete_user_data(login)
        elif command == "set_limit":
            login   = input("Login: ")
            mem_inp = input("New limit in bytes (0 = block, e.g. 1073741824 = 1GB): ").strip()
            if mem_inp.lstrip("-").isdigit():
                ok = update_user_by_login(login, size_of_memory=float(mem_inp))
                print("Updated" if ok else "Failed")
            else:
                print("Invalid value")
        else:
            print("Unknown command")