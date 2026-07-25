-- Data-quality fixes found in vendors / components / vendor_components audit (2026-07-21)
-- Run against genspark_erp. Take a backup first: mysqldump genspark_erp > backup_before_fix.sql

START TRANSACTION;

-- 1) [APPLIED 2026-07-21] Merged orphaned duplicate category "Cabinet" (id=7, 0 components)
--    into the actually-used "Case" category (id=16): backfilled slugs on Case/Cooling and
--    deleted the unreferenced Cabinet row. Also fixed the two seed scripts that would have
--    recreated it (init_db.py, app/utils/schema.py) — both seeded 'Cabinet' by slug lookup
--    and were missing 'Case'/'Cooling' entirely, so a fresh install would have silently
--    lacked 2 of the 8 required build categories.
-- (kept here for reference / re-applying on other environments)
DELETE FROM component_categories WHERE id = 7 AND id NOT IN (SELECT DISTINCT category_id FROM components);
UPDATE component_categories SET slug = 'case' WHERE id = 16 AND (slug IS NULL OR slug = '');
UPDATE component_categories SET slug = 'cooling' WHERE id = 17 AND (slug IS NULL OR slug = '');

-- 2) Fix the broken vendor listing: quantity=0 AND price=NULL (unsellable, but still visible).
--    Option A (recommended): remove the dead listing entirely since it has no valid price.
DELETE FROM vendor_components WHERE id = 1 AND quantity = 0 AND price IS NULL;

--    Option B (alternative): if this vendor still stocks the item, restore it instead of deleting:
-- UPDATE vendor_components
-- SET price = (SELECT price FROM components WHERE id = vendor_components.component_id), quantity = 5
-- WHERE id = 1;

-- 3) Fill missing specs on the 2 GPUs flagged with specs = NULL.
--    Placeholder JSON — replace with real spec sheets before going live.
UPDATE components SET specs = JSON_OBJECT('memory', '8GB GDDR6', 'interface', 'PCIe 4.0', 'note', 'specs pending vendor confirmation')
WHERE id = 143 AND specs IS NULL;   -- NVIDIA GeForce RTX 3050 8GB

UPDATE components SET specs = JSON_OBJECT('memory', '6GB GDDR6', 'interface', 'PCIe 3.0', 'note', 'specs pending vendor confirmation')
WHERE id = 144 AND specs IS NULL;   -- NVIDIA GeForce GTX 1660 SUPER 6GB

COMMIT;

-- 4) Components missing brand_id (48 rows) — needs a real brand mapping, not a blind default.
--    Run this SELECT to review before writing, then fill in per-row UPDATEs (name -> brand):
SELECT id, name, category_id
FROM components
WHERE brand_id IS NULL
ORDER BY category_id, name;

-- Example pattern once brand ids are confirmed against the `brands` table:
-- UPDATE components c
-- JOIN brands b ON b.brand_name = 'AMD'
-- SET c.brand_id = b.brand_id
-- WHERE c.brand_id IS NULL AND c.name LIKE 'AMD %';

-- 5) `products` table is dead (1 orphan row, no FK to vendors/components, unused by the
--    build flow). Confirm nothing references it before dropping:
-- SELECT * FROM products;
-- DROP TABLE products;   -- only after confirming no app code queries it
