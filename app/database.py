from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database path detection for both Docker and bare metal
def get_database_url():
    # Check if we're in Docker environment
    if os.path.exists('/app') and os.path.exists('/home/app'):
        # Docker environment - use /app/data (mounted volume)
        data_dir = '/app/data'
        try:
            # Test write permissions
            test_file = f'{data_dir}/.write_test'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✅ Using Docker data directory: {data_dir}")
            return f"sqlite:///{data_dir}/food_cost.db"
        except Exception as e:
            print(f"❌ Docker data directory {data_dir} not writable: {e}")
            print("⚠️  Using /tmp as fallback (NOT PERSISTENT)")
            return "sqlite:////tmp/food_cost.db"
    else:
        # Bare metal environment
        data_dir = './data'
        try:
            os.makedirs(data_dir, mode=0o755, exist_ok=True)
            print(f"✅ Using bare metal data directory: {data_dir}")
        except Exception as e:
            print(f"⚠️  Could not create data directory {data_dir}: {e}")
        
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