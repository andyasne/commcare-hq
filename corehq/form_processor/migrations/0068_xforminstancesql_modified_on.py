# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-17 09:22
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0067_auto_20170915_1506'),
    ]

    operations = [
        # done in 2 stages to avoid setting the value for all existing data
        migrations.AddField(
            model_name='xforminstancesql',
            name='server_modified_on',
            field=models.DateTimeField(null=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='server_modified_on',
            field=models.DateTimeField(auto_now=True, db_index=True, null=True),
        ),
    ]
