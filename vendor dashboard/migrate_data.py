#!/usr/bin/env python3
"""
Copy catalog data from local MySQL to Railway MySQL.

Reads local credentials from vendor dashboard/.env (DB_*).
Reads Railway credentials from environment variables (see below).

Default tables (with automatic name resolution):
  components  -> components
  products    -> products, else ecom_products
  prebuilt    -> prebuilt, else pc_builds
  users, vendors, cart, cart_items (+ FK deps: roles, categories, brands, etc.)

Related FK tables are migrated first automatically (roles before users, users before
vendors, catalog tables before cart_items, etc.).

Usage (PowerShell, from vendor dashboard folder):
  pip install pymysql python-dotenv
  $env:RAILWAY_MYSQL_PASSWORD = "your_mysql_root_password"
  python migrate_data.py

Full sync (catalog + vendors + cart):
  $env:MIGRATE_TABLES = "users,vendors,vendor_components,cart,cart_items,components,products,prebuilt"
  python migrate_data.py

Optional env overrides:
  LOCAL_DB_HOST, LOCAL_DB_PORT, LOCAL_DB_USER, LOCAL_DB_PASSWORD, LOCAL_DB_NAME
  RAILWAY_DB_HOST, RAILWAY_DB_PORT, RAILWAY_DB_USER, RAILWAY_DB_PASSWORD, RAILWAY_DB_NAME
  MIGRATE_TABLES=components,products,prebuilt
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")
# Optional: Railway-only secrets (do not commit). Overrides nothing in .env for local DB.
load_dotenv(SCRIPT_DIR / ".env.railway")

# Logical names -> possible physical table names (first match wins)
TABLE_ALIASES: dict[str, list[str]] = {
    "roles": ["roles"],
    "users": ["users"],
    "vendors": ["vendors"],
    "vendor_components": ["vendor_components"],
    "vendor_documents": ["vendor_documents"],
    "cart": ["cart"],
    "cart_items": ["cart_items"],
    "components": ["components"],
    "products": ["products", "ecom_products"],
    "prebuilt": ["prebuilt", "pc_builds"],
}

# Extra tables pulled in so FK inserts succeed (direct deps per requested table)
DEPENDENCY_TABLES: dict[str, list[str]] = {
    "users": ["roles"],
    "vendors": ["roles", "users"],
    "vendor_components": ["roles", "users", "vendors", "component_categories", "brands", "components"],
    "vendor_documents": ["roles", "users", "vendors"],
    "components": ["component_categories", "brands"],
    "prebuilt": ["build_components", "component_categories", "brands", "components"],
    "pc_builds": ["build_components", "component_categories", "brands", "components"],
    "cart": ["roles", "users"],
    "cart_items": [
        "roles",
        "users",
        "vendors",
        "component_categories",
        "brands",
        "components",
        "pc_builds",
        "build_components",
        "cart",
    ],
}

MIGRATION_ORDER = [
    "roles",
    "users",
    "vendors",
    "vendor_documents",
    "vendor_components",
    "component_categories",
    "brands",
    "components",
    "products",
    "ecom_products",
    "prebuilt",
    "pc_builds",
    "build_components",
    "cart",
    "cart_items",
]


def _env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


def local_config() -> dict[str, Any]:
    return {
        "host": _env("LOCAL_DB_HOST", "DB_HOST", default="localhost"),
        "port": int(_env("LOCAL_DB_PORT", "DB_PORT", default="3306")),
        "user": _env("LOCAL_DB_USER", "DB_USER", default="root"),
        "password": _env("LOCAL_DB_PASSWORD", "DB_PASSWORD"),
        "database": _env("LOCAL_DB_NAME", "DB_NAME", default="genspark_erp"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }


def railway_config() -> dict[str, Any]:
    # Do not fall back to local DB_PASSWORD — it is not the Railway MySQL password.
    password = _env(
        "RAILWAY_DB_PASSWORD",
        "RAILWAY_MYSQL_PASSWORD",
        "MYSQL_ROOT_PASSWORD",
        "MYSQLPASSWORD",
        "MYSQL_PASSWORD",
    )
    if not password:
        print(
            "ERROR: Railway password not set.\n"
            "  PowerShell: $env:RAILWAY_MYSQL_PASSWORD = 'paste from Railway MySQL → MYSQL_ROOT_PASSWORD'\n"
            "  Or create vendor dashboard/.env.railway with:\n"
            "    RAILWAY_MYSQL_PASSWORD=...\n"
            "    MYSQLHOST=centerbeam.proxy.rlwy.net\n"
            "    MYSQLPORT=41753\n"
            "    MYSQLDATABASE=railway",
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "host": _env("RAILWAY_DB_HOST", "MYSQLHOST", default="centerbeam.proxy.rlwy.net"),
        "port": int(_env("RAILWAY_DB_PORT", "MYSQLPORT", default="41753")),
        "user": _env("RAILWAY_DB_USER", "MYSQLUSER", default="root"),
        "password": password,
        "database": _env("RAILWAY_DB_NAME", "MYSQLDATABASE", default="railway"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }


def connect(cfg: dict[str, Any], label: str) -> pymysql.connections.Connection:
    try:
        conn = pymysql.connect(**cfg)
        print(f"Connected to {label}: {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")
        return conn
    except pymysql.Error as exc:
        print(f"ERROR: Could not connect to {label}: {exc}", file=sys.stderr)
        sys.exit(1)


def table_exists(conn: pymysql.connections.Connection, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = %s
            LIMIT 1
            """,
            (table,),
        )
        return cur.fetchone() is not None


def resolve_table(conn: pymysql.connections.Connection, logical: str) -> str | None:
    for candidate in TABLE_ALIASES.get(logical, [logical]):
        if table_exists(conn, candidate):
            return candidate
    return None


def _row_key(row: dict[str, Any], name: str) -> Any:
    """Read information_schema field regardless of MySQL/pymysql key casing."""
    if name in row:
        return row[name]
    upper, lower = name.upper(), name.lower()
    if upper in row:
        return row[upper]
    if lower in row:
        return row[lower]
    raise KeyError(name)


def get_columns(conn: pymysql.connections.Connection, table: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, column_key, extra, data_type
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        rows = list(cur.fetchall())
    # Normalize to lowercase keys for the rest of the script
    return [
        {
            "column_name": _row_key(r, "column_name"),
            "column_key": _row_key(r, "column_key"),
            "extra": _row_key(r, "extra"),
            "data_type": _row_key(r, "data_type"),
        }
        for r in rows
    ]


def get_primary_key(columns: list[dict[str, Any]]) -> list[str]:
    return [c["column_name"] for c in columns if c["column_key"] == "PRI"]


def serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, bytes):
        return value
    return value


def fetch_rows(conn: pymysql.connections.Connection, table: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM `{table}`")
        return list(cur.fetchall())


def upsert_rows(
    dest: pymysql.connections.Connection,
    table: str,
    rows: list[dict[str, Any]],
    pk_cols: list[str],
) -> tuple[int, int]:
    if not rows:
        return 0, 0

    columns = list(rows[0].keys())
    col_list = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    update_cols = [c for c in columns if c not in pk_cols]
    if update_cols:
        update_clause = ", ".join(f"`{c}` = VALUES(`{c}`)" for c in update_cols)
        sql = (
            f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {update_clause}"
        )
    else:
        sql = f"INSERT IGNORE INTO `{table}` ({col_list}) VALUES ({placeholders})"

    inserted = 0
    with dest.cursor() as cur:
        for row in rows:
            values = [serialize_value(row.get(c)) for c in columns]
            cur.execute(sql, values)
            # rowcount: 1 = insert, 2 = update, 0 = no change (ignore)
            if cur.rowcount == 1:
                inserted += 1
    dest.commit()
    return inserted, len(rows)


def migrate_table(
    local: pymysql.connections.Connection,
    remote: pymysql.connections.Connection,
    local_table: str,
    remote_table: str | None = None,
) -> None:
    remote_table = remote_table or local_table

    if not table_exists(local, local_table):
        print(f"  SKIP (not on local): {local_table}")
        return
    if not table_exists(remote, remote_table):
        print(f"  SKIP (not on Railway): {remote_table}")
        return

    local_cols = {c["column_name"] for c in get_columns(local, local_table)}
    remote_cols = {c["column_name"] for c in get_columns(remote, remote_table)}
    shared = sorted(local_cols & remote_cols)
    if not shared:
        print(f"  SKIP (no shared columns): {local_table} -> {remote_table}")
        return

    pk_cols = [
        c["column_name"]
        for c in get_columns(remote, remote_table)
        if c["column_key"] == "PRI" and c["column_name"] in shared
    ]
    if not pk_cols:
        print(f"  WARN: No primary key on Railway table `{remote_table}`; using INSERT IGNORE only.")

    with local.cursor() as cur:
        col_sql = ", ".join(f"`{c}`" for c in shared)
        cur.execute(f"SELECT {col_sql} FROM `{local_table}`")
        rows = list(cur.fetchall())

    inserted, total = upsert_rows(remote, remote_table, rows, pk_cols)
    print(f"  {local_table} -> {remote_table}: {total} row(s), ~{inserted} new insert(s)")


def build_plan(conn: pymysql.connections.Connection, logical_tables: list[str]) -> list[str]:
    physical: dict[str, str] = {}
    for logical in logical_tables:
        resolved = resolve_table(conn, logical)
        if resolved:
            physical[logical] = resolved
        else:
            print(f"WARN: Could not resolve table for '{logical}' on local DB.")

    plan: list[str] = []
    for logical, table in physical.items():
        for dep in DEPENDENCY_TABLES.get(logical, []) + DEPENDENCY_TABLES.get(table, []):
            if table_exists(conn, dep) and dep not in plan:
                plan.append(dep)
        if table not in plan:
            plan.append(table)

    ordered: list[str] = []
    for name in MIGRATION_ORDER:
        if name in plan and name not in ordered:
            ordered.append(name)
    for name in plan:
        if name not in ordered:
            ordered.append(name)
    return ordered


def main() -> None:
    logical = [
        t.strip()
        for t in _env("MIGRATE_TABLES", default="components,products,prebuilt").split(",")
        if t.strip()
    ]

    local = connect(local_config(), "local MySQL")
    remote = connect(railway_config(), "Railway MySQL")

    try:
        plan = build_plan(local, logical)
        if not plan:
            print("Nothing to migrate. Check table names and local database.")
            sys.exit(1)

        print("\nMigration plan:", ", ".join(plan))
        print("-" * 50)
        for table in plan:
            migrate_table(local, remote, table)
        print("-" * 50)
        print("Migration completed successfully!")
    finally:
        local.close()
        remote.close()


if __name__ == "__main__":
    main()
