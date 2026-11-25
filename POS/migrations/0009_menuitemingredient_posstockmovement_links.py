from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("POS", "0008_receipt_cogs"),
        ("inventory", "0007_productpackaging"),
    ]

    operations = [
        migrations.CreateModel(
            name="MenuItemIngredient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=12)),
                ("client_id", models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ingredients", to="POS.menuitem")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="used_in_recipes", to="inventory.product")),
            ],
            options={
                "ordering": ["product__name"],
            },
        ),
        migrations.AddField(
            model_name="posstockmovement",
            name="menu_item",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="POS.menuitem"),
        ),
        migrations.AddField(
            model_name="posstockmovement",
            name="order_item",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="POS.orderitem"),
        ),
        migrations.AlterField(
            model_name="posstockmovement",
            name="quantity",
            field=models.DecimalField(decimal_places=3, max_digits=12),
        ),
        migrations.AddConstraint(
            model_name="menuitemingredient",
            constraint=models.UniqueConstraint(fields=("menu_item", "product"), name="unique_menu_item_ingredient_product"),
        ),
    ]
