# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-26 10:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projman', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projmanuser',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='/media/uploads/photos/%Y/%m/%d'),
        ),
    ]