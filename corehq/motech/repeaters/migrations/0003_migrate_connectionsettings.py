from django.db import migrations

from corehq.motech.repeaters.dbaccessors import iter_repeaters


def _migrate_to_connectionsettings(apps, schema_editor):
    for repeater in iter_repeaters():
        if not repeater.connection_settings_id:
            repeater.create_connection_settings()


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0002_sqlrepeatrecord'),
        ('motech', '0007_auto_20200909_2138'),
    ]

    operations = [
        migrations.RunPython(_migrate_to_connectionsettings,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
