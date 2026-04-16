from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import settings
import time

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")

engine = None

for i in range(10):
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            pass
        print("Database connected successfully")
        break
    except Exception as e:
        print(f"DB not ready, retrying... ({i+1}/10): {e}")
        time.sleep(2)

if engine is None:
    raise Exception("Database connection failed after retries")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()