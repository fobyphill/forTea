# Generated by Django 4.0.2 on 2023-12-22 13:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_datatypeslist_mainpageconst_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassTypesList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('description', models.CharField(max_length=50)),
            ],
        ),
        migrations.AlterField(
            model_name='registrator',
            name='date_update',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='registratorlog',
            name='date_update',
            field=models.DateTimeField(),
        ),
    ]