# Generated by Django 1.11.22 on 2019-11-01 22:02

from django.db import migrations, models

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.models import LinkedApplication
from corehq.apps.app_manager.suite_xml.post_process.resources import add_xform_resource_overrides
from corehq.apps.linked_domain.applications import get_master_app_by_version
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _add_overrides_for_all_builds(apps, schema_editor):
    app_ids = (get_doc_ids_by_class(LinkedApplication)
               + get_deleted_doc_ids_by_class(LinkedApplication))
    iter_update(LinkedApplication.get_db(), _add_overrides_for_build, with_progress_bar(app_ids), chunksize=1)


def _add_overrides_for_build(doc):
    linked_build = wrap_app(doc)
    if not linked_build.upstream_app_id or not linked_build.upstream_version:
        return

    master_build = get_master_app_by_version(linked_build.domain_link, linked_build.upstream_app_id,
                                             linked_build.upstream_version)
    if not master_build:
        return

    linked_map = _get_xmlns_map(linked_build)
    master_map = _get_xmlns_map(master_build)
    override_map = {
        master_form_unique_id: linked_map[xmlns]
        for xmlns, master_form_unique_id in master_map.items() if xmlns in linked_map
    }
    add_xform_resource_overrides(linked_build.domain, linked_build.get_id, override_map)


def _get_xmlns_map(app):
    return {
        f.xmlns: f.unique_id
        for m in app.get_modules() for f in app.get_forms() if f.form_type != 'shadow_form'
    }


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0007_add_linked_app_fields_to_es'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResourceOverride',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('app_id', models.CharField(max_length=255)),
                ('root_name', models.CharField(max_length=32)),
                ('pre_id', models.CharField(max_length=255)),
                ('post_id', models.CharField(max_length=255)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='resourceoverride',
            unique_together=set([('domain', 'app_id', 'root_name', 'pre_id')]),
        ),
        migrations.RunPython(_add_overrides_for_all_builds,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
