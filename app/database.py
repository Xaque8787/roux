from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Smart database path detection for both Docker and bare metal
def get_database_url():
    # Check if we're in Docker environment
    if os.path.exists('/app/data'):
        # Docker environment - ensure directory is writable
        try:
            # Try to create the directory if it doesn't exist
            os.makedirs('/app/data', mode=0o755, exist_ok=True)
            # Test write permissions
            test_file = '/app/data/.write_test'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("Docker data directory is writable")
        except Exception as e:
            print(f"Warning: Docker data directory not writable: {e}")
        
        return os.getenv("DATABASE_URL", "sqlite:///app/data/food_cost.db")
    else:
        # Bare metal environment - create data directory if it doesn't exist
        data_dir = './data'
        try:
            os.makedirs(data_dir, mode=0o755, exist_ok=True)
            print(f"Created data directory: {data_dir}")
        except Exception as e:
            print(f"Warning: Could not create data directory {data_dir}: {e}")
        
        return os.getenv("DATABASE_URL", "sqlite:///./data/food_cost.db")

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