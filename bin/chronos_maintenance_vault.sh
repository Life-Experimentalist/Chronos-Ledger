#!/bin/sh
# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
#
# chronos_maintenance_vault.sh
# Runs integrity checks and creates compressed database backups.

set -e

BACKUP_DIR="/var/chronos/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATABASE_URL="${DATABASE_URL:-postgresql://chronos_admin:SecureCloud2026@localhost:5432/chronos_ledger}"

echo "============================================================"
echo " Chronos Ledger — Structural Integrity Check"
echo " Timestamp: $TIMESTAMP"
echo "============================================================"

# 1. Timetable collision audit
echo "\n[1/3] Running timetable collision audit..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 << 'EOF'
DO $$
DECLARE
    collision_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO collision_count
    FROM daily_ledger dl1
    JOIN daily_ledger dl2
        ON dl1.target_date = dl2.target_date
        AND dl1.id < dl2.id
        AND dl1.active_lead_id = dl2.active_lead_id
        AND dl1.active_lead_id IS NOT NULL
    JOIN structural_master_slots sms1 ON dl1.master_slot_id = sms1.id
    JOIN structural_master_slots sms2 ON dl2.master_slot_id = sms2.id
    WHERE dl1.operational_state != 'ON_LEAVE'
      AND dl2.operational_state != 'ON_LEAVE'
      AND (sms1.time_window_start, sms1.time_window_end)
          OVERLAPS (sms2.time_window_start, sms2.time_window_end);

    IF collision_count > 0 THEN
        RAISE WARNING 'CRITICAL: % timetable collision(s) detected', collision_count;
    ELSE
        RAISE NOTICE 'OK: No timetable collisions detected';
    END IF;
END $$;
EOF

# 2. Generate compressed backup
echo "\n[2/3] Generating database snapshot..."
mkdir -p "$BACKUP_DIR"
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/chronos_ledger_snap_$TIMESTAMP.sql.gz"
echo " Snapshot written: $BACKUP_DIR/chronos_ledger_snap_$TIMESTAMP.sql.gz"

# 3. Retention policy (90-day window)
echo "\n[3/3] Applying retention policy (90 days)..."
find "$BACKUP_DIR" -type f -mtime +90 -name "*.sql.gz" -delete -print | head -20

echo "\n============================================================"
echo " Maintenance complete."
echo "============================================================"
