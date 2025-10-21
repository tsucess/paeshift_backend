from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='has_2fa_enabled',
            field=models.BooleanField(
                default=False,
                help_text="Whether two-factor authentication is enabled for this user",
                verbose_name="2FA enabled",
            ),
        ),
    ]
