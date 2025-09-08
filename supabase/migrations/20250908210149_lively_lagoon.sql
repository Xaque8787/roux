/*
# Add assigned_employee_ids column to tasks table

1. Schema Changes
   - Add `assigned_employee_ids` column to `tasks` table
   - Column stores comma-separated list of employee IDs for multi-employee task assignment

2. Purpose
   - Enable multiple employees to be assigned to a single task
   - Support team-based task completion with proper wage calculation
   - Maintain backward compatibility with existing single-employee assignments

3. Data Type
   - String column to store comma-separated employee IDs
   - Nullable to maintain compatibility with existing records
*/

-- Add the assigned_employee_ids column to the tasks table
ALTER TABLE tasks ADD COLUMN assigned_employee_ids TEXT;