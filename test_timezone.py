#!/usr/bin/env python3
"""
Test script to verify timezone configuration is working correctly.
Run this inside the Docker container to verify TZ environment variable.
"""

import os
from datetime import datetime
import zoneinfo

def test_timezone_config():
    print("=" * 60)
    print("TIMEZONE CONFIGURATION TEST")
    print("=" * 60)

    # Check TZ environment variable
    tz_env = os.getenv('TZ', 'NOT SET')
    print(f"\n1. TZ Environment Variable: {tz_env}")

    # Check available timezone
    try:
        if tz_env != 'NOT SET':
            tz = zoneinfo.ZoneInfo(tz_env)
            print(f"   ✓ Timezone is valid and available")
        else:
            tz = None
            print(f"   ⚠ TZ not set, will default to UTC")
    except zoneinfo.ZoneInfoNotFoundError:
        print(f"   ✗ Timezone '{tz_env}' not found!")
        tz = None

    # Show current time in configured timezone
    if tz:
        now_aware = datetime.now(tz)
        print(f"\n2. Current Time (Timezone-Aware):")
        print(f"   {now_aware.isoformat()}")
        print(f"   Timezone: {now_aware.tzname()}")
        print(f"   UTC Offset: {now_aware.strftime('%z')}")
    else:
        now_aware = datetime.now(zoneinfo.ZoneInfo('UTC'))
        print(f"\n2. Current Time (UTC - fallback):")
        print(f"   {now_aware.isoformat()}")

    # Show naive datetime (what gets stored in database)
    now_naive = now_aware.replace(tzinfo=None)
    print(f"\n3. Naive Timestamp (Stored in DB):")
    print(f"   {now_naive.isoformat()}")
    print(f"   Note: This represents local wall-clock time")

    # Demonstrate the timer calculation
    print(f"\n4. Timer Display Logic:")
    print(f"   JavaScript receives: '{now_naive.isoformat()}'")
    print(f"   JavaScript parses as: new Date('{now_naive.isoformat()}')")
    print(f"   Browser interprets this as LOCAL TIME (not UTC)")
    print(f"   If browser is in same timezone as server, timer works correctly!")

    # Show what would happen with UTC interpretation
    if tz:
        utc_offset_hours = now_aware.utcoffset().total_seconds() / 3600
        print(f"\n5. Common Mistake (Adding 'Z'):")
        print(f"   If we append 'Z': '{now_naive.isoformat()}Z'")
        print(f"   JavaScript treats this as UTC")
        print(f"   Timer would start at: {abs(utc_offset_hours):.0f} hours (the UTC offset)")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_timezone_config()
