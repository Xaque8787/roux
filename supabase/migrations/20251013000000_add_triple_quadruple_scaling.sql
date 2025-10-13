/*
  # Add Triple and Quadruple Batch Scaling Options

  1. Changes
    - Add `scale_triple` column to `batches` table (boolean, default false)
    - Add `scale_quadruple` column to `batches` table (boolean, default false)

  2. Purpose
    - Allows batches to be scaled up by 3x and 4x in addition to existing scaling options
    - Provides more flexibility for batch production scaling
*/

-- Add scale_triple column to batches table
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'batches' AND column_name = 'scale_triple'
  ) THEN
    ALTER TABLE batches ADD COLUMN scale_triple BOOLEAN DEFAULT false;
  END IF;
END $$;

-- Add scale_quadruple column to batches table
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'batches' AND column_name = 'scale_quadruple'
  ) THEN
    ALTER TABLE batches ADD COLUMN scale_quadruple BOOLEAN DEFAULT false;
  END IF;
END $$;
