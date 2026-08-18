from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_payment_prediction_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='proof',
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
    ]
