# GenSpark System

Full Stack platform for PC Builds – **Python (Flask) + MySQL + AdminLTE** – with Admin & Vendor dashboards.  
**Target:** Pakistan (local). **Currency:** PKR (Rs. – Pakistani Rupee).

## Tech Stack

- **Backend:** Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Bcrypt
- **Database:** MySQL
- **Frontend:** Jinja2 templates, AdminLTE 3 (Bootstrap 4), Font Awesome

## Modules

1. **Authentication & Roles** – Login/Signup, Admin / Vendor / Customer
2. **Vendor Management** – Registration, Admin approval, Pending/Approved/Blocked
3. **Component Inventory** – Categories, Components, Stock, Price
4. **PC Builds** – Predefined builds (Gaming/Office/Budget), Build components
5. **Custom Builds** – User config (tables: custom_builds, custom_build_components)
6. **Order Management** – Orders, Order items, Status: Pending → Accepted → Assembly → QA → Shipped → Delivered
7. **Assembly Tracking** – Vendor updates: In Assembly, Testing, Completed
8. **Quality Assurance** – Admin Pass/Fail, notes
9. **Payment** – Payments, transactions
10. **Shipment** – Courier, tracking number, status
11. **Notifications** – (table ready)
12. **Analytics/Reports** – Revenue, orders by status, top vendors

## Setup

### 1. Create MySQL database

```sql
CREATE DATABASE genspark_erp;
```

### 2. Environment

Copy `.env.example` to `.env` and set:

- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `SECRET_KEY` (and optional `JWT_SECRET_KEY`)

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize database

```bash
python init_db.py
```

This creates tables, seeds roles (admin, vendor, customer), component categories, and default admin:

- **Email:** admin@genspark.com  
- **Password:** admin123  

### 5. Run app

```bash
python run.py
```

Open: `http://127.0.0.1:5000`

- **Login:** `/auth/login`
- **Admin panel:** `/admin/` (after login as admin)
- **Vendor panel:** `/vendor/` (after login as vendor)

## Workflow

- **Customer:** Signup → Select PC → Order → Payment → Assembly → QA → Shipment → Delivery  
- **Vendor:** Login → Profile (approval) → Accept Order → Assembly → Update status → Ship  
- **Admin:** Approve vendors → Monitor orders → QA Pass/Fail → Reports  

## Project structure

```
vendor dashboard/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── auth/                 # Login, Signup, Logout
│   ├── admin/                # Admin panel routes
│   ├── vendor/               # Vendor panel routes
│   ├── models/               # SQLAlchemy models (users, vendors, components, orders, etc.)
│   └── templates/            # AdminLTE templates (admin/, vendor/, auth/)
├── config.py
├── run.py
├── init_db.py
├── requirements.txt
└── .env.example
```

## Default URLs

| Panel   | URL           |
|--------|----------------|
| Home   | /              |
| Login  | /auth/login    |
| Signup | /auth/signup   |
| Admin  | /admin/        |
| Vendor | /vendor/       |

GenSpark – Final Year / Portfolio / Industry-level project.
