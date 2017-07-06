# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-28 14:58
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0045_drop_case_modified_since'),
    ]

    operations = [
         migrator.get_migration('get_related_indices.sql'),
    ]
