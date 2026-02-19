#!/usr/bin/env python3
"""
In-place SQLite migration for UzhavanGo.

- Creates a timestamped backup before applying changes.
- Adds missing columns/tables/indexes without dropping existing data.
- Backfills booking.owner_id from tractors.owner_id.
- Handles legacy schemas (for example, users.name -> users.full_name).

Usage:
  ./venv/bin/python scripts/migrate_sqlite_inplace.py --db instance/uzhavango.db
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def index_exists(cur: sqlite3.Cursor, index: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (index,),
    ).fetchone()
    return row is not None


def add_column_if_missing(cur: sqlite3.Cursor, table: str, ddl_suffix: str, column: str) -> None:
    if not table_exists(cur, table):
        return
    if column_exists(cur, table, column):
        return
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl_suffix}")


def rename_column_if_possible(cur: sqlite3.Cursor, table: str, old_name: str, new_name: str) -> bool:
    if not table_exists(cur, table):
        return False
    if not column_exists(cur, table, old_name) or column_exists(cur, table, new_name):
        return False
    try:
        cur.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
        return True
    except sqlite3.OperationalError:
        return False


def ensure_users_columns(cur: sqlite3.Cursor) -> None:
    if not table_exists(cur, "users"):
        return

    # Legacy DBs may have "name" instead of "full_name".
    renamed = rename_column_if_possible(cur, "users", "name", "full_name")
    if not renamed and not column_exists(cur, "users", "full_name"):
        add_column_if_missing(cur, "users", "full_name TEXT NOT NULL DEFAULT ''", "full_name")
        if column_exists(cur, "users", "name"):
            cur.execute(
                "UPDATE users SET full_name = COALESCE(NULLIF(name, ''), full_name) "
                "WHERE full_name IS NULL OR full_name = ''"
            )

    add_column_if_missing(cur, "users", "phone TEXT NOT NULL DEFAULT ''", "phone")
    add_column_if_missing(cur, "users", "is_verified_owner INTEGER NOT NULL DEFAULT 0", "is_verified_owner")
    add_column_if_missing(cur, "users", "last_login TEXT", "last_login")


def create_payments_table_if_missing(cur: sqlite3.Cursor) -> None:
    if table_exists(cur, "payments"):
        return
    cur.execute(
        """
        CREATE TABLE payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL UNIQUE,
            receipt_number TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL,
            farmer_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'paid',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY(farmer_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def create_platform_settings_table_if_missing(cur: sqlite3.Cursor) -> None:
    if table_exists(cur, "platform_settings"):
        return
    cur.execute(
        """
        CREATE TABLE platform_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )


def create_chat_messages_table_if_missing(cur: sqlite3.Cursor) -> None:
    if table_exists(cur, "chat_messages"):
        return
    cur.execute(
        """
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def create_booking_addons_table_if_missing(cur: sqlite3.Cursor) -> None:
    if table_exists(cur, "booking_addons"):
        return
    cur.execute(
        """
        CREATE TABLE booking_addons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            addon_tractor_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            total_price REAL NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY(addon_tractor_id) REFERENCES tractors(id) ON DELETE CASCADE
        )
        """
    )


def create_indexes(cur: sqlite3.Cursor) -> None:
    wanted = {
        "ix_tractors_pincode": "CREATE INDEX ix_tractors_pincode ON tractors(pincode)",
        "ix_bookings_owner_status": "CREATE INDEX ix_bookings_owner_status ON bookings(owner_id, status)",
        "ix_payments_owner": "CREATE INDEX ix_payments_owner ON payments(owner_id)",
        "ix_tractors_equipment_type": "CREATE INDEX ix_tractors_equipment_type ON tractors(equipment_type)",
        "ix_tractors_availability_status": "CREATE INDEX ix_tractors_availability_status ON tractors(availability_status)",
        "ix_chat_messages_booking": "CREATE INDEX ix_chat_messages_booking ON chat_messages(booking_id, created_at)",
        "ix_booking_addons_booking": "CREATE INDEX ix_booking_addons_booking ON booking_addons(booking_id)",
        "ix_users_last_login": "CREATE INDEX ix_users_last_login ON users(last_login)",
    }
    for name, ddl in wanted.items():
        if not index_exists(cur, name):
            cur.execute(ddl)

    # Farmers use phone-first login. Keep phone unique inside farmer role.
    if not index_exists(cur, "uq_users_phone_farmer"):
        duplicate_farmer_phone = cur.execute(
            """
            SELECT phone, COUNT(*)
            FROM users
            WHERE lower(role)='farmer' AND phone IS NOT NULL AND phone != ''
            GROUP BY phone
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        ).fetchone()
        if duplicate_farmer_phone is None:
            cur.execute(
                "CREATE UNIQUE INDEX uq_users_phone_farmer ON users(phone) WHERE lower(role)='farmer'"
            )
        else:
            print("Skipped uq_users_phone_farmer index due to duplicate farmer phone data.")


def backfill_owner_id(cur: sqlite3.Cursor) -> None:
    if not table_exists(cur, "bookings") or not table_exists(cur, "tractors"):
        return
    if not column_exists(cur, "bookings", "owner_id"):
        return
    cur.execute(
        """
        UPDATE bookings
        SET owner_id = (
            SELECT t.owner_id
            FROM tractors t
            WHERE t.id = bookings.tractor_id
        )
        WHERE owner_id IS NULL OR owner_id = 0
        """
    )


def normalize_booking_status(cur: sqlite3.Cursor) -> None:
    if not table_exists(cur, "bookings") or not column_exists(cur, "bookings", "status"):
        return
    cur.execute("UPDATE bookings SET status='pending' WHERE lower(status)='requested'")
    cur.execute("UPDATE bookings SET status='working' WHERE lower(status)='in_progress'")


def ensure_default_platform_settings(cur: sqlite3.Cursor) -> None:
    if not table_exists(cur, "platform_settings"):
        return
    defaults = {
        "commission_pct": "10",
        "surge_threshold": "5",
    }
    for key, value in defaults.items():
        cur.execute(
            """
            INSERT INTO platform_settings(key, value, created_at, updated_at)
            SELECT ?, ?, datetime('now'), datetime('now')
            WHERE NOT EXISTS (SELECT 1 FROM platform_settings WHERE key = ?)
            """,
            (key, value, key),
        )


def run(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup = db_path.with_name(f"{db_path.name}.migration-backup-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(db_path, backup)
    print(f"Backup created: {backup}")

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        cur.execute("PRAGMA foreign_keys=ON")

        ensure_users_columns(cur)

        add_column_if_missing(cur, "tractors", "pincode TEXT NOT NULL DEFAULT ''", "pincode")
        add_column_if_missing(cur, "tractors", "village TEXT", "village")
        add_column_if_missing(cur, "tractors", "district TEXT", "district")
        add_column_if_missing(cur, "tractors", "average_rating REAL NOT NULL DEFAULT 0", "average_rating")
        add_column_if_missing(cur, "tractors", "equipment_type TEXT NOT NULL DEFAULT 'Tractor'", "equipment_type")
        add_column_if_missing(cur, "tractors", "availability_status TEXT NOT NULL DEFAULT 'available'", "availability_status")

        add_column_if_missing(cur, "bookings", "owner_id INTEGER", "owner_id")
        add_column_if_missing(cur, "bookings", "paid_at TEXT", "paid_at")
        add_column_if_missing(cur, "bookings", "surge_multiplier REAL NOT NULL DEFAULT 1", "surge_multiplier")
        add_column_if_missing(cur, "bookings", "commission_pct REAL NOT NULL DEFAULT 10", "commission_pct")
        add_column_if_missing(cur, "bookings", "commission_amount REAL NOT NULL DEFAULT 0", "commission_amount")
        add_column_if_missing(cur, "bookings", "owner_payout_amount REAL NOT NULL DEFAULT 0", "owner_payout_amount")
        add_column_if_missing(cur, "bookings", "shared_group_code TEXT", "shared_group_code")
        add_column_if_missing(cur, "bookings", "en_route_at TEXT", "en_route_at")
        add_column_if_missing(cur, "bookings", "farmer_confirmed_at TEXT", "farmer_confirmed_at")
        add_column_if_missing(cur, "bookings", "completion_confirmed_hours INTEGER", "completion_confirmed_hours")
        add_column_if_missing(cur, "bookings", "total_base_price REAL NOT NULL DEFAULT 0", "total_base_price")
        add_column_if_missing(cur, "bookings", "total_addon_price REAL NOT NULL DEFAULT 0", "total_addon_price")
        add_column_if_missing(cur, "bookings", "grand_total REAL NOT NULL DEFAULT 0", "grand_total")

        create_payments_table_if_missing(cur)
        create_platform_settings_table_if_missing(cur)
        create_chat_messages_table_if_missing(cur)
        create_booking_addons_table_if_missing(cur)
        create_indexes(cur)

        backfill_owner_id(cur)
        normalize_booking_status(cur)
        ensure_default_platform_settings(cur)

        con.commit()
        print("Migration completed successfully.")
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="instance/uzhavango.db", help="Path to sqlite db file")
    args = parser.parse_args()
    run(Path(args.db))


if __name__ == "__main__":
    main()
