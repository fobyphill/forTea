# Generated by Django 4.0.2 on 2024-03-19 14:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_mainpageconst_user_login'),
    ]

    operations = [
        migrations.AlterField(
            model_name='techprocess',
            name='settings',
            field=models.JSONField(default={'system': False}),
        ),
    ]
