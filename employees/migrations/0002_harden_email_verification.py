import datetime

from django.db import migrations, models
from django.utils import timezone


def set_default_expiry(apps, schema_editor):
    EmailVerification = apps.get_model("employees", "EmailVerification")
    EmailVerification.objects.all().update(
        expires_at=timezone.now() + datetime.timedelta(minutes=30)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailverification",
            name="pin",
            field=models.CharField(max_length=128),
        ),
        migrations.AddField(
            model_name="emailverification",
            name="attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="emailverification",
            name="expires_at",
            field=models.DateTimeField(default=timezone.now),
        ),
        migrations.RunPython(set_default_expiry, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="emailverification",
            name="expires_at",
            field=models.DateTimeField(),
        ),
    ]
