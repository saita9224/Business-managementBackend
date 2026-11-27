# Generated manually to fix reason field nullability

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0009_rename_inventory_s_reason_03e330_idx_inventory_s_reason__9f061c_idx_and_more'),
    ]

    operations = [
        # Alter the reason field to be nullable
        migrations.AlterField(
            model_name='stockmovement',
            name='reason',
            field=models.ForeignKey(
                help_text='The reason for this stock movement',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='movements',
                to='inventory.stockmovementreason'
            ),
        ),
    ]
