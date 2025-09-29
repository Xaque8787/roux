from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Smart database path detection for both Docker and bare metal
def get_database_url():
    # Ensure data directory exists for bare metal deployments
    if not os.path.exists('/app/data'):
        # Bare metal environment - create data directory if it doesn't exist
        data_dir = './data'
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
                print(f"Created data directory: {data_dir}")
            except Exception as e:
                print(f"Warning: Could not create data directory {data_dir}: {e}")
        
        return os.getenv("DATABASE_URL", "sqlite:///./data/food_cost.db")
    else:
        # Docker environment - use absolute path
        return os.getenv("DATABASE_URL", "sqlite:////app/data/food_cost.db")

DATABASE_URL = get_database_url()
print(f"Using database URL: {DATABASE_URL}")

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