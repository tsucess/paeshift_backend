
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0011_payment_verified_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='payment_provider',
            field=models.CharField(blank=True, choices=[('paystack', 'Paystack'), ('flutterwave', 'Flutterwave'), ('other', 'Other')], help_text='Source payment provider (e.g., paystack, flutterwave)', max_length=20, null=True),
        ),
    ]
