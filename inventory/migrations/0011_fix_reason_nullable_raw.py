# Generated manually to fix reason field nullability with raw SQL

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0010_fix_reason_nullable'),
    ]

    operations = [
        # Use raw SQL to alter the column to be nullable
        migrations.RunSQL(
            sql="""
                ALTER TABLE inventory_stockmovement 
                ALTER COLUMN reason_id DROP NOT NULL;
            """,
            reverse_sql="""
                ALTER TABLE inventory_stockmovement 
                ALTER COLUMN reason_id SET NOT NULL;
            """,
        ),
    ]
