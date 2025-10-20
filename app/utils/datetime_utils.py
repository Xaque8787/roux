from datetime import datetime, timezone
import os
import zoneinfo

def get_current_time():
    """
    Get current time in configured timezone.
    Falls back to UTC if TZ environment variable is not set.
    """
    tz_name = os.getenv('TZ', 'UTC')
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        tz = timezone.utc
    return datetime.now(tz)

def get_naive_local_time():
    """
    Get current time as naive datetime in configured timezone.
    This is used for SQLite compatibility which doesn't support timezone-aware datetimes.
    """
    aware_time = get_current_time()
    return aware_time.replace(tzinfo=None)
