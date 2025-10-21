# Timezone Fix for Timer Display Issue

## Problem

When running the app in Docker, task timers would start at 7:00:00 (7 hours) and count upward, but upon completion would show the correct duration (e.g., 10 minutes).

## Root Cause

This was a **timezone handling issue** with three components:

1. **Server**: Stores naive timestamps (no timezone info) in the configured timezone via `TZ` environment variable (Pacific Time: UTC-7)
2. **JavaScript**: The old code appended 'Z' to timestamps, forcing JavaScript to interpret them as UTC
3. **Result**: A timestamp like `14:00:00` Pacific would be interpreted as `14:00:00 UTC`, which is actually `07:00:00` Pacific - a 7 hour difference!

### Why Completion Time Was Correct

The completion time calculation worked because it computed the difference between two timestamps:
- Both start and end times had the same 7-hour offset applied
- The difference (duration) was correct: `(14:00 UTC - 7:00 UTC) = 7 hours` vs `(14:00 PT - 7:00 PT) = 7 hours`

But the **running timer** compared:
- Start time: interpreted as UTC (wrong)
- Current time: actual browser local time (correct)
- This created a 7-hour initial offset

## Solution

### 1. Fixed JavaScript Timer Code (`templates/inventory_day.html`)

**Changed from:**
```javascript
const startTime = new Date(startedAt + (startedAt.includes('Z') ? '' : 'Z'));
```

**To:**
```javascript
const startTime = new Date(startedAt);
```

**Why this works:**
- Server sends timestamps like `2025-10-21T14:00:00` (no timezone indicator)
- JavaScript's `new Date()` interprets this as **local browser time**
- Since both server and browser are in the same timezone (Pacific), the timestamp represents the same moment in time
- Timer shows correct elapsed time from that moment to now

### 2. Enhanced Dockerfile (`Dockerfile`)

Added timezone support:
```dockerfile
# Install tzdata for timezone support
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

# Set default timezone
ENV TZ=America/Los_Angeles
```

**Why this is important:**
- Ensures Python's `zoneinfo` module can find timezone data
- Provides a default timezone that matches the expected deployment region
- Can be overridden via docker-compose or runtime environment variables

### 3. Docker Compose Already Configured

The `docker-compose.yml` already has:
```yaml
environment:
  - TZ=${TZ:-America/Los_Angeles}
```

This allows users to:
- Use their host system's timezone: `TZ=$(cat /etc/timezone) docker-compose up`
- Override with any timezone: `TZ=America/New_York docker-compose up`
- Default to Pacific Time if not specified

## Key Concepts

### Naive vs Aware Datetimes

- **Naive**: No timezone info, represents "wall clock time" (what you see on a clock)
- **Aware**: Has timezone info, represents an absolute point in time

This app uses **naive datetimes** because:
1. SQLite doesn't natively support timezone-aware datetimes
2. All users are expected to be in the same timezone
3. Simpler to reason about for local business operations

### JavaScript Date Parsing

When JavaScript parses an ISO datetime string:
- **With 'Z'**: `2025-10-21T14:00:00Z` → Treated as UTC
- **Without timezone**: `2025-10-21T14:00:00` → Treated as **local browser timezone**

Our fix leverages this behavior to ensure timestamps are interpreted consistently.

## Testing

To verify the fix works:

1. **Start a task** - Timer should start at 0:00
2. **Wait 1 minute** - Timer should show ~1:00
3. **Complete the task** - Should show 1 minute duration
4. **Check different timezones**:
   ```bash
   TZ=America/New_York docker-compose up
   TZ=Europe/London docker-compose up
   ```

## Migration Impact

This fix:
- ✅ Requires no database migration
- ✅ No changes to stored data
- ✅ Backward compatible with existing timestamps
- ✅ Works with any timezone configuration

## Future Considerations

If the app needs to support **multiple timezones** (e.g., corporate offices in different regions):

1. Switch to timezone-aware datetimes
2. Store all times in UTC
3. Convert to user's timezone for display
4. Consider using PostgreSQL instead of SQLite for better timezone support
