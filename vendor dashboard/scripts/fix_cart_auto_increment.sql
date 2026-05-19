-- Run on Railway MySQL after data migration (fixes AUTO_INCREMENT vs migrated IDs).
-- Usage (MySQL client): SOURCE fix_cart_auto_increment.sql;
-- Or paste each ALTER into Railway MySQL console.

SET @next_cart = (SELECT IFNULL(MAX(id), 0) + 1 FROM `cart`);
SET @sql_cart = CONCAT('ALTER TABLE `cart` AUTO_INCREMENT = ', @next_cart);
PREPARE stmt FROM @sql_cart;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @next_items = (SELECT IFNULL(MAX(id), 0) + 1 FROM `cart_items`);
SET @sql_items = CONCAT('ALTER TABLE `cart_items` AUTO_INCREMENT = ', @next_items);
PREPARE stmt FROM @sql_items;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @next_ecart = (SELECT IFNULL(MAX(id), 0) + 1 FROM `ecom_carts`);
SET @sql_ecart = CONCAT('ALTER TABLE `ecom_carts` AUTO_INCREMENT = ', @next_ecart);
PREPARE stmt FROM @sql_ecart;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @next_eitems = (SELECT IFNULL(MAX(id), 0) + 1 FROM `ecom_cart_items`);
SET @sql_eitems = CONCAT('ALTER TABLE `ecom_cart_items` AUTO_INCREMENT = ', @next_eitems);
PREPARE stmt FROM @sql_eitems;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verify:
-- SELECT TABLE_NAME, AUTO_INCREMENT FROM information_schema.TABLES
--   WHERE TABLE_SCHEMA = DATABASE()
--     AND TABLE_NAME IN ('cart', 'cart_items', 'ecom_carts', 'ecom_cart_items');
