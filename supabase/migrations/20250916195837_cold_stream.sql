/*
# Add price per weight/volume fields to ingredients table

1. Schema Changes
   - Add `uses_price_per_weight_volume` boolean column to track pricing method
   - Add `price_per_weight_volume` decimal column to store the price per unit

2. Purpose
   - Enable persistence of price per weight/volume pricing method
   - Store the original price per unit for editing and reference
   - Maintain backward compatibility with existing ingredients

3. Data Type
   - Boolean for pricing method flag (defaults to false)
   - Decimal for price per unit (nullable for backward compatibility)
*/

-- Add the price per weight/volume fields to the ingredients table
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS uses_price_per_weight_volume BOOLEAN DEFAULT FALSE;
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS price_per_weight_volume DECIMAL(10,4);