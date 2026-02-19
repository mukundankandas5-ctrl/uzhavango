## SQLite in-place migration

Use this when your local DB has old table/column shapes and the app raises schema errors.

### Run

```bash
cd /Users/mukundankandasamy/Desktop/UZHAVANGO
./venv/bin/python scripts/migrate_sqlite_inplace.py --db instance/uzhavango.db
```

### What it does

- Creates a timestamped backup next to the DB file.
- Adds missing columns used by the current app (`users.phone`, `tractors.pincode`, etc.).
- Adds advanced marketplace columns (`availability_status`, `equipment_type`, commission/surge fields, completion confirmation fields).
- Repairs legacy `users.name` by renaming/backfilling to `users.full_name`.
- Creates required tables if missing: `payments`, `platform_settings`, `booking_participants`, `chat_messages`.
- Backfills `bookings.owner_id` from tractor owner data.

This script is idempotent. You can run it again safely.
