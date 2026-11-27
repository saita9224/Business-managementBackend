# Backfill stock movement reasons from the legacy `reason` varchar column,
# link movements to StockMovementReason rows, then drop the orphaned column.
#
# The legacy column was never part of the migration state (the FK `reason`
# field maps to `reason_id`), so this must be done with raw SQL.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0011_fix_reason_nullable_raw'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- 1. Copy legacy reason codes into reason_code
                UPDATE inventory_stockmovement
                SET reason_code = reason
                WHERE reason IS NOT NULL
                  AND reason <> ''
                  AND (reason_code IS NULL OR reason_code = '');

                -- 2. Link movements to their StockMovementReason row
                UPDATE inventory_stockmovement sm
                SET reason_id = r.id
                FROM inventory_stockmovementreason r
                WHERE r.code = sm.reason_code
                  AND sm.reason_id IS NULL;

                -- 3. Flush deferred FK trigger events so ALTER TABLE is allowed
                SET CONSTRAINTS ALL IMMEDIATE;

                -- 4. Drop the orphaned legacy column
                ALTER TABLE inventory_stockmovement
                DROP COLUMN IF EXISTS reason;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
