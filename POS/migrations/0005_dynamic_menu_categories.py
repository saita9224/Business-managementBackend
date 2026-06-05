from django.db import migrations, models


DEFAULT_CATEGORIES = [
    ("food", "Food"),
    ("drinks", "Drinks"),
    ("snacks", "Snacks"),
    ("other", "Other"),
]


def label_from_key(key):
    return " ".join(part.capitalize() for part in key.replace("-", " ").split())


def seed_menu_categories(apps, schema_editor):
    MenuCategory = apps.get_model("POS", "MenuCategory")
    MenuItem = apps.get_model("POS", "MenuItem")

    for key, label in DEFAULT_CATEGORIES:
        MenuCategory.objects.get_or_create(
            key=key,
            defaults={"label": label},
        )

    existing_keys = (
        MenuItem.objects
        .exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
    )
    for key in existing_keys:
        MenuCategory.objects.get_or_create(
            key=key,
            defaults={"label": label_from_key(key)},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("POS", "0004_menuitem_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="MenuCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["label"],
            },
        ),
        migrations.AlterField(
            model_name="menuitem",
            name="category",
            field=models.CharField(default="other", max_length=80),
        ),
        migrations.RunPython(seed_menu_categories, migrations.RunPython.noop),
    ]
