# Testing the Database Locking Fix

## Changes Applied

1. **src/core/db.py**: Added WAL mode and 30-second busy timeout configuration
2. **CLAUDE.md**: Updated documentation to reflect WAL mode configuration

## How to Test

### Step 1: Rebuild Docker Images

```bash
docker compose build
```

This will rebuild both API and worker containers with the updated database configuration.

### Step 2: Start Services

```bash
docker compose up
```

Watch the logs to ensure both services start successfully.

### Step 3: Verify WAL Mode is Enabled

Open a new terminal and run:

```bash
docker compose exec api python -c "
import sqlite3
conn = sqlite3.connect('/data/cs2bot.db')
cursor = conn.cursor()
cursor.execute('PRAGMA journal_mode')
journal_mode = cursor.fetchone()[0]
cursor.execute('PRAGMA busy_timeout')
busy_timeout = cursor.fetchone()[0]
print(f'Journal mode: {journal_mode}')
print(f'Busy timeout: {busy_timeout} ms')
cursor.close()
conn.close()
"
```

**Expected output:**
```
Journal mode: wal
Busy timeout: 30000 ms
```

### Step 4: Test Concurrent Operations

**Test Scenario**: Delete a watch while the worker is processing

1. **Access Admin Panel**: Open http://localhost:8000/admin/watches in your browser

2. **Start Worker**: Ensure the worker is running and processing watches
   ```bash
   docker compose logs -f worker
   ```
   You should see logs like:
   ```
   Worker starting up
   Processing watch: ...
   ```

3. **Try to Delete a Watch**: While the worker is actively processing:
   - Go to the admin panel
   - Click "Delete" on any watch
   - Submit the deletion

**Expected Result**:
- ✅ Deletion should succeed without "database is locked" error
- ✅ Watch should be removed from the list
- ✅ Worker should continue processing without interruption

**Previous Behavior** (without fix):
- ❌ 500 Internal Server Error
- ❌ Error: "sqlite3.OperationalError: database is locked"

### Step 5: Test Update Operations

1. **Edit a Watch**: Try updating a watch's rules while worker is running
   - Click "Edit" on a watch
   - Modify any field (e.g., change min_profit_usd)
   - Save changes

**Expected Result**:
- ✅ Update should succeed immediately
- ✅ Changes should be saved to database
- ✅ No "database is locked" errors

### Step 6: Check WAL Files

Verify that WAL mode files are created:

```bash
docker compose exec api ls -lah /data/
```

**Expected output** should include:
```
-rw-r--r--  cs2bot.db       # Main database file
-rw-r--r--  cs2bot.db-wal   # Write-Ahead Log file
-rw-r--r--  cs2bot.db-shm   # Shared memory file
```

These additional files are normal and required for WAL mode operation.

### Step 7: Monitor Performance

Watch the logs for any database-related errors:

```bash
# Watch API logs
docker compose logs -f api

# Watch worker logs
docker compose logs -f worker
```

**Expected behavior:**
- No "database is locked" errors
- No unusual delays in admin operations
- Worker continues processing without interruption

## Troubleshooting

### If WAL mode is not enabled

If you see `Journal mode: delete` instead of `wal`, try:

1. Stop all containers:
   ```bash
   docker compose down
   ```

2. Remove the database volume (WARNING: This will delete all data):
   ```bash
   docker volume rm cs2bot_sqlite-data
   ```

3. Restart services:
   ```bash
   docker compose up
   ```

The database will be recreated with WAL mode enabled.

### If you still get "database is locked" errors

1. Check that both containers are using the same database file:
   ```bash
   docker compose exec api ls -l /data/cs2bot.db
   docker compose exec worker ls -l /data/cs2bot.db
   ```

2. Verify busy_timeout is set:
   ```bash
   docker compose exec api python -c "
   import sqlite3
   conn = sqlite3.connect('/data/cs2bot.db')
   cursor = conn.cursor()
   cursor.execute('PRAGMA busy_timeout')
   print('Busy timeout:', cursor.fetchone()[0], 'ms')
   "
   ```

3. Check for long-running queries in worker logs

## Success Criteria

✅ **Fix is working if:**
- Can delete watches while worker is running
- Can update watches while worker is running
- No "database is locked" errors in logs
- WAL mode is confirmed as enabled
- Both services operate concurrently without blocking

## Next Steps

If the fix resolves the locking issues:
- ✅ Keep the changes
- ✅ Monitor production for any new issues
- ✅ Delete this test file: `rm TEST_DATABASE_FIX.md`

If issues persist:
- Consider implementing Solution B: Shorter worker transactions
- Or Solution C: Migrate to PostgreSQL for better concurrency
