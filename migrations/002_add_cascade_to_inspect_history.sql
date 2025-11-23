-- Add ON DELETE CASCADE to inspect_history.watchlist_id foreign key
-- This allows watchlist entries to be deleted even when they have related inspect_history records

-- Drop the existing foreign key constraint
ALTER TABLE inspect_history
  DROP CONSTRAINT IF EXISTS inspect_history_watchlist_id_fkey;

-- Re-add the foreign key with ON DELETE CASCADE
ALTER TABLE inspect_history
  ADD CONSTRAINT inspect_history_watchlist_id_fkey
  FOREIGN KEY (watchlist_id)
  REFERENCES watchlist(id)
  ON DELETE CASCADE;
