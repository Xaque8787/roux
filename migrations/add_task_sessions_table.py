"""
Migration: Add task_sessions table

This migration adds a new task_sessions table to track individual work sessions
for tasks. This enables:
- Reopening completed tasks and tracking additional time
- Detailed session history for tasks
- More accurate time tracking across multiple work periods

Changes:
1. Creates task_sessions table with columns:
   - id (primary key)
   - task_id (foreign key to tasks)
   - started_at (datetime, when session started)
   - ended_at (datetime, when session ended, nullable for active sessions)
   - pause_duration (integer, total seconds paused during this session)
   - created_at (datetime, record creation timestamp)

2. Adds foreign key constraint from task_sessions to tasks table

Note: The Task model will automatically use sessions for time calculations
when they exist, maintaining backward compatibility with existing tasks.
"""

from sqlalchemy import create_engine, Column, Integer, DateTime, ForeignKey, text
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/food_cost.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS task_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                pause_duration INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
            )
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_task_sessions_task_id ON task_sessions (task_id)
        """))

if __name__ == "__main__":
    upgrade()
    print("Migration completed: task_sessions table created")
