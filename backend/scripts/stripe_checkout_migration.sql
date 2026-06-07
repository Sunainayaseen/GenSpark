-- GenSpark Stripe checkout — run once in MySQL Workbench (database: genspark_erp)
-- Maps tutorial "products" to existing `components` (id, name, stock, price).

-- Optional demo table (tutorial schema); catalog checkout uses `components` instead.
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    stock_quantity INT NOT NULL CHECK (stock_quantity >= 0)
);

-- Extend ERP orders for Stripe (safe to re-run: ignore "Duplicate column" errors)
ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'Pending';
ALTER TABLE orders ADD COLUMN stripe_txn_id VARCHAR(255) NULL;
ALTER TABLE orders ADD UNIQUE INDEX uq_orders_stripe_txn (stripe_txn_id);

-- Seed demo row for integration test (products table)
INSERT INTO products (id, product_name, stock_quantity)
VALUES (1, 'Demo Stripe Product', 5)
ON DUPLICATE KEY UPDATE product_name = VALUES(product_name), stock_quantity = VALUES(stock_quantity);

-- Or seed components catalog (preferred for real checkout):
-- INSERT INTO components (name, category_id, price, stock) VALUES ('Demo CPU', 1, 15000, 5);
