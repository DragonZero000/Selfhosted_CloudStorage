from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, insert, select
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime

Base = declarative_base()
engine = create_engine("postgresql://postgres:pass@localhost:5432/appdb")
SessionLocal = sessionmaker(bind=engine)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    login = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    size_of_memory = Column(Float)
Base.metadata.create_all(bind=engine)

def get_user_data(login):
    session = SessionLocal()
    result = session.query(User).filter_by(login=login).first()
    session.close()
    return result

def get_users_data():
    session = SessionLocal()
    result = session.query(User).all()
    session.close()
    return result

def insert_user_data(login, password, size_of_memory=0):
    session = SessionLocal()
    try:
        session.add(User(login=login, password_hash=password, created_at=datetime.now(), size_of_memory=size_of_memory))
        session.commit()
    except Exception as e:
        session.rollback()
        print(e)
    finally:
        session.close()

def delete_user_data(login):
    session = SessionLocal()
    user = session.query(User).filter_by(login=login).first()
    if not user:
        print("user not found")
        return
    confirmation = input("Are you sure you want to delete this user? (y/N): ").strip() or "N"
    if confirmation == "y" or confirmation == "Y":
        session.delete(user)
        session.commit()
    elif confirmation == "n" or confirmation == "N":
        session.rollback()
    else:
        print("Invalid input")
        return
    session.close()

if __name__ == "__main__":
    print("Input command: ", end="")
    command = input()
    while command != "exit":
        if command == "get_user_data":
            login = input("Login: ")
            res = get_user_data(login)
            print(res.id, res.login, res.created_at, res.size_of_memory)
        elif command == "get_users_data":
            res = get_users_data()
            for user in res:
                print(user.id ,user.login, user.created_at, user.size_of_memory)
        elif command == "insert_user_data":
            print("debug version") # отредактировать данное исполнение комманды
            login = input("Login: ")
            password = input("Password: ")
            size_of_memory = input("Size of memory: ")
            if size_of_memory == "":
                insert_user_data(login, password)
            else:
                insert_user_data(login, password, size_of_memory)
        elif command == "delete_user_data":
            login = input("Login: ")
            delete_user_data(login)
        elif command == "command_list" or command == "help":
            print("get_user_data")
            print("get_users_data")
            print("insert_user_data")
            print("delete_user_data")
        else:
            print("Invalid command")
        print("Input command: ", end="")
        command = input()