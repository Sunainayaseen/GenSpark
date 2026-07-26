-- GenSpark ERP — minimal reference/lookup data.
-- Safe to share: contains no user accounts, orders, or other PII.
-- For a working demo admin/vendor login, run backend/init_db.py instead —
-- it seeds fresh password hashes rather than shipping static ones here.

INSERT INTO `roles` VALUES (1,'admin'),(2,'vendor'),(3,'customer'),(4,'rider');

INSERT INTO `component_categories` VALUES
  (1,'Processor','processor'),(2,'RAM','ram'),(3,'GPU','gpu'),
  (4,'Motherboard','motherboard'),(5,'Storage','storage'),(6,'PSU','psu'),
  (7,'Cabinet','cabinet'),(12,'Monitor',NULL),(13,'Keyboard',NULL),
  (14,'Mouse',NULL),(16,'Case',NULL),(17,'Cooling',NULL),
  (18,'Mouse','mouse'),(19,'Keyboard','keyboard'),(20,'Monitor','monitor');

INSERT INTO `brands` VALUES (1,'HP'),(2,'Dell'),(3,'Lenovo');
INSERT INTO `component_brands` VALUES (1,'HP'),(2,'Dell'),(3,'Lenovo');
