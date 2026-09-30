# TexPOS - POS Billing Software

A Flask + SQLite implementation of the supplied technical interview task.

## Features
- Admin portal: dashboard, product CRUD, staff management, returns, suppliers, ledger and reports.
- Billing portal: product search, cart, discount/tax, Cash/UPI/Card payment selection, stock deduction and printable invoice.
- Role-based authentication: Admin and Staff.
- Responsive Admin portal: the same `/dashboard` and admin routes become a mobile-app-style responsive web layout on small screens.
- SQLite database with sales, sale items, returns and ledger tables.

## Run locally
```bash
python -m venv venv
# Windows: venv\\Scripts\\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Test credentials
- Admin: `admin` / `admin123`
- Staff: `staff` / `staff123`

## Suggested demo URLs
- Login: `/login`
- Admin dashboard: `/dashboard`
- Billing: `/billing`
- Products: `/products`
- Staff: `/staff`
- Suppliers: `/suppliers`
- Returns: `/returns`
- Ledger: `/ledger`
- Reports: `/reports`

## Deployment
For a public demo, deploy to Render/Railway/PythonAnywhere or another Flask host. Set `SECRET_KEY` and use persistent storage for SQLite, or migrate the DB to PostgreSQL for production.
