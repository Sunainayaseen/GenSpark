-- Run this in MySQL (e.g. MySQL Workbench) if component save fails with brand_id error.
-- First select your database:
USE genspark_erp;

-- Step 1: Add column (run only once; if column already exists, you'll get an error - skip to Step 2)
ALTER TABLE components ADD COLUMN brand_id INT NULL;

-- Step 2: Add foreign key to brands table (run only once)
ALTER TABLE components
  ADD CONSTRAINT fk_components_brand
  FOREIGN KEY (brand_id) REFERENCES brands(brand_id) ON DELETE SET NULL;
