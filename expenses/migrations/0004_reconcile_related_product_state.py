# State-only migration: the database column was already renamed to
# related_product_id outside of migration history (applied directly on
# the VPS). This records the rename in Django's migration state so the
# model (related_product) and migration state agree, without emitting
# any ALTER TABLE that would fail on databases already migrated.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0003_expenseitem_client_id_expensepayment_client_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name='expenseitem',
                    old_name='product',
                    new_name='related_product',
                ),
            ],
            database_operations=[],
        ),
    ]
