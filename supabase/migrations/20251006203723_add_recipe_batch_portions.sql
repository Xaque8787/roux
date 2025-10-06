/*
  # Add Recipe Batch Portions Table

  This migration adds support for recipes to include portions of other recipes (via batches) as ingredients.

  1. New Tables
    - `recipe_batch_portions`
      - `id` (integer, primary key)
      - `recipe_id` (integer, foreign key to recipes)
      - `batch_id` (integer, foreign key to batches)
      - `portion_size` (float, nullable) - Size of the portion when using fixed amounts
      - `portion_unit` (varchar, nullable) - Unit of measurement for the portion
      - `use_recipe_portion` (boolean, default false) - Whether to use percentage-based portions
      - `recipe_portion_percent` (float, nullable) - Percentage of recipe as decimal (0.25 = 25%)

  2. Purpose
    - Allows recipes to reference other recipes as ingredients through batches
    - Supports both fixed portion sizes (e.g., "2 cups") and percentage-based portions (e.g., "25% of recipe")
    - Enables accurate cost calculations when recipes build upon other recipes

  3. Notes
    - Similar structure to dish_batch_portions but for recipes
    - Either portion_size/portion_unit OR recipe_portion_percent should be used, not both
    - When use_recipe_portion is true, recipe_portion_percent is used for calculations
    - When use_recipe_portion is false, portion_size and portion_unit are used
*/

CREATE TABLE IF NOT EXISTS recipe_batch_portions (
  id SERIAL PRIMARY KEY,
  recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
  batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
  portion_size DOUBLE PRECISION,
  portion_unit VARCHAR(50),
  use_recipe_portion BOOLEAN DEFAULT FALSE,
  recipe_portion_percent DOUBLE PRECISION,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recipe_batch_portions_recipe_id ON recipe_batch_portions(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_batch_portions_batch_id ON recipe_batch_portions(batch_id);
