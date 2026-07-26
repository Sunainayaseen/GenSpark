# GenSpark Database

MySQL (SQLite fallback for local dev/tests — see `backend/config.py`).

## Files

- `genspark_erp_full_export.sql` — full `mysqldump` of the actual working
  database (39 tables, all real data: users, orders, vendors, catalog).
  Exported via MySQL Workbench Data Export. **Use this one for a complete,
  working restore.**
- `schema.sql` — table structure only (37 tables — predates two newer
  Stripe-related tables), no data rows. Safe to share publicly.
- `sample_data.sql` — minimal reference/lookup data only (roles, component
  categories, brands). No user accounts, orders, or other personal data.

## Setup (full restore, recommended)

```sql
CREATE DATABASE genspark_erp;
```

```bash
mysql -u root -p genspark_erp < database/genspark_erp_full_export.sql
```

## Setup (structure only, no data)

```bash
mysql -u root -p genspark_erp < database/schema.sql
mysql -u root -p genspark_erp < database/sample_data.sql
```

Then seed a working default admin/vendor login (fresh password hashes,
not shipped statically in this repo):

```bash
cd backend
python init_db.py
```

Default accounts created by `init_db.py`: `admin@genspark.com` / `admin123`
and `vendor@genspark.com` / `vendor123` (development only — production
deploys generate a random one-time password instead, see
`backend/app/utils/schema.py`).
