from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['user', 'status'], name='api_pay_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='prediction',
            index=models.Index(fields=['user', 'game'], name='api_pred_user_game_idx'),
        ),
    ]
