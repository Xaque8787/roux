import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

def get_backup_dir() -> str:
    if os.getenv("DOCKER_ENV"):
        backup_dir = "/app/data/backups"
    else:
        backup_dir = "./data/backups"

    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    return backup_dir

def get_database_path() -> str:
    if os.getenv("DOCKER_ENV"):
        return "/app/data/food_cost.db"
    else:
        return "./data/food_cost.db"

def create_backup() -> Dict[str, str]:
    try:
        db_path = get_database_path()
        backup_dir = get_backup_dir()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = Path(backup_dir) / backup_filename

        source = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(str(backup_path))

        source.backup(backup_conn)

        backup_conn.close()
        source.close()

        file_size = backup_path.stat().st_size

        logger.info(f"Backup created successfully: {backup_filename}")

        return {
            "success": True,
            "filename": backup_filename,
            "size": file_size,
            "timestamp": timestamp
        }
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def cleanup_old_backups(keep_count: int = 7) -> int:
    try:
        backup_dir = get_backup_dir()
        backup_files = sorted(
            Path(backup_dir).glob("backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        deleted_count = 0
        for old_backup in backup_files[keep_count:]:
            old_backup.unlink()
            deleted_count += 1
            logger.info(f"Deleted old backup: {old_backup.name}")

        return deleted_count
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return 0

def list_backups() -> List[Dict[str, any]]:
    try:
        backup_dir = get_backup_dir()
        backup_files = sorted(
            Path(backup_dir).glob("backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        backups = []
        for backup_file in backup_files:
            stat = backup_file.stat()
            timestamp_str = backup_file.stem.replace("backup_", "")

            try:
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_date = timestamp_str

            backups.append({
                "filename": backup_file.name,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": formatted_date,
                "timestamp": stat.st_mtime
            })

        return backups
    except Exception as e:
        logger.error(f"Failed to list backups: {str(e)}")
        return []

def restore_backup(backup_filename: str) -> Dict[str, str]:
    try:
        import shutil

        backup_dir = get_backup_dir()
        backup_path = Path(backup_dir) / backup_filename

        if not backup_path.exists():
            return {
                "success": False,
                "error": "Backup file not found"
            }

        db_path = get_database_path()
        db_path_obj = Path(db_path)

        # Create a safety backup of the current database before restoring
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_backup_filename = f"pre_restore_safety_{timestamp}.db"
        safety_backup_path = Path(backup_dir) / safety_backup_filename

        if db_path_obj.exists():
            # Use file copy for safety backup - faster and doesn't require DB connection
            shutil.copy2(db_path, safety_backup_path)
            logger.info(f"Created safety backup: {safety_backup_filename}")

        # Close any existing SQLite connections by opening and closing
        # This ensures the database file is not locked
        try:
            temp_conn = sqlite3.connect(db_path)
            temp_conn.close()
        except:
            pass

        # Restore using file copy - this is more reliable than SQLite backup
        # when the database might have active connections from SQLAlchemy
        shutil.copy2(backup_path, db_path)

        # Verify the restore by opening a connection
        verify_conn = sqlite3.connect(db_path)
        cursor = verify_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        verify_conn.close()

        logger.info(f"Database restored from: {backup_filename}")

        return {
            "success": True,
            "message": f"Database restored successfully from {backup_filename}. Please restart the application for changes to take full effect.",
            "safety_backup": safety_backup_filename
        }
    except Exception as e:
        logger.error(f"Restore failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
