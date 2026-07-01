from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_passwordresetrequest"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pendingregistration",
            name="pin",
            field=models.CharField(max_length=128),
        ),
        migrations.AddField(
            model_name="pendingregistration",
            name="attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="passwordresetrequest",
            name="pin",
            field=models.CharField(max_length=128),
        ),
        migrations.AddField(
            model_name="passwordresetrequest",
            name="attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
