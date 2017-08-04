import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def confirm(self):
        return raw_input("Continue?\n(y/n)") == 'y'

    def get_data_fields(self):
        data_model = CustomDataFieldsDefinition.get_or_create(
            self.domain,
            UserFieldsView.field_type,
        )
        return sorted(data_model.fields)

    def handle(self, domain, **options):
        self.domain = domain
        self.locations_by_id = {
            loc.location_id: loc for loc in SQLLocation.objects.filter(domain=domain)
        }
        filename = 'agency_users.csv'
        self.data_fields = self.get_data_fields()
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'user_id',
                'username',
                'first_name',
                'last_name',
                'virtual_location_id',
                'assigned_location_id',
                'location_id',
                'location_name',
                'phone_number',
                'email',
                'language',
            ] + [
                'data: {}'.format(field.slug) for field in self.data_fields
            ])
            for user in CommCareUser.by_domain(domain):
                self.add_user(user, writer)
        print "Wrote to {}".format(filename)

    def add_user(self, user, writer):
        if (user.user_data.get('usertype', None) not in ['pcp', 'pcc-chemist', 'plc', 'pac']
                or user.user_data.get('user_level', None) != 'real'):
            return

        virtual_location_id = user.user_location_id
        assigned_location_id = user.location_id

        location_id = virtual_location_id or assigned_location_id
        location = self.locations_by_id.get(location_id, None) if location_id else None
        if not location:
            print "user {} {} has no location".format(user.username, user._id)
            return

        writer.writerow([
            user._id,
            user.raw_username,
            user.first_name,
            user.last_name,
            # We expect this to ALWAYS be set
            virtual_location_id,
            assigned_location_id,
            location_id,
            location.name,
            user.phone_number,
            user.email,
            user.language,
        ] + [
            user.user_data.get(field, '') for field in self.data_fields
        ])
