# Generated by Django 4.0.2 on 2024-01-26 14:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_alter_mainpageaddress_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='mainpageconst',
            name='user_login',
            field=models.BooleanField(default=True),
        ),
    ]