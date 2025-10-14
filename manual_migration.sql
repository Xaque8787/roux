-- Manual migration script to add snapshot columns to tasks table
-- Run this with: sqlite3 data/food_cost.db < manual_migration.sql

-- Add snapshot_quantity column
ALTER TABLE tasks ADD COLUMN snapshot_quantity REAL;

-- Add snapshot_par_level column
ALTER TABLE tasks ADD COLUMN snapshot_par_level REAL;

-- Add snapshot_override_create column
ALTER TABLE tasks ADD COLUMN snapshot_override_create BOOLEAN DEFAULT 0;

-- Add snapshot_override_no_task column
ALTER TABLE tasks ADD COLUMN snapshot_override_no_task BOOLEAN DEFAULT 0;

-- Verify columns were added
.schema tasks
