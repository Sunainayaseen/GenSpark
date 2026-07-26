-- GenSpark — peripheral products (keyboard, mouse, monitor, RAM)
-- Run after products + custom_builds tables exist:
--   mysql -u root -p genspark_erp < vendor dashboard/scripts/seed_products_peripherals.sql

USE genspark_erp;

INSERT INTO products (name, category, price, stock) VALUES
('Redragon S101 Gaming Keyboard', 'Keyboard', 4500.00, 20),
('Logitech G102 Lightsync Gaming Mouse', 'Mouse', 5500.00, 25),
('Ease E22V10 22 Inch 75Hz Monitor', 'Monitor', 18500.00, 10),
('Kingston FURY Beast 8GB DDR4 3200MHz', 'RAM', 6200.00, 40);
