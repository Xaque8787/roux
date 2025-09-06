-- Add item count pricing support to ingredients table
-- This migration adds the use_item_count_pricing column and updates related fields

-- Add the new column for item count pricing
ALTER TABLE ingredients ADD COLUMN use_item_count_pricing BOOLEAN DEFAULT FALSE;

-- Update existing ingredients to have default values for new fields
UPDATE ingredients SET use_item_count_pricing = FALSE WHERE use_item_count_pricing IS NULL;