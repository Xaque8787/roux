from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Smart database path detection for both Docker and bare metal
def get_database_url():
    # Check if we're in Docker (look for container-specific paths)
    if os.path.exists('/app/data'):
        # Docker environment - use absolute path
        return os.getenv("DATABASE_URL", "sqlite:///app/data/food_cost.db")
    else:
        # Bare metal environment - use relative path
        return os.getenv("DATABASE_URL", "sqlite:///./data/food_cost.db")

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()