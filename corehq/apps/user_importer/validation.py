from abc import ABCMeta, abstractmethod
from collections import Counter

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.importer import is_password
from corehq.apps.users.util import normalize_username
from dimagi.utils.parsing import string_to_boolean


def get_user_import_validators(domain_obj, all_specs):
    domain = domain_obj.name
    validate_passwords = domain_obj.strong_mobile_passwords
    return [
        UsernameValidator(domain),
        IsActive(domain),
        UsernameOrUserIdRequired(domain),
        Duplicates(domain, 'username', all_specs),
        Duplicates(domain, 'user_id', all_specs),
        Duplicates(domain, 'password', all_specs, is_password) if validate_passwords else NoopValidator(domain),
    ]


class ImportValidator(metaclass=ABCMeta):
    error_message = None

    def __init__(self, domain):
        self.domain = domain

    def __call__(self, spec):
        error = self.validate_spec(spec)
        if error:
            raise UserUploadError(error)

    @abstractmethod
    def validate_spec(self, spec):
        raise NotImplementedError


class NoopValidator(ImportValidator):
    def validate_spec(self, spec):
        pass


class UsernameValidator(ImportValidator):
    error_message = _('username cannot contain spaces or symbols')

    def validate_spec(self, spec):
        username = spec.get('username')
        try:
            normalize_username(str(username), self.domain)
        except TypeError:
            pass
        except ValidationError:
            return self.error_message


class IsActive(ImportValidator):
    error_message = _("'is_active' column can only contain 'true' or 'false'")

    def validate_spec(self, spec):
        is_active = spec.get('is_active')
        if isinstance(is_active, str):
            try:
                string_to_boolean(is_active) if is_active else None
            except ValueError:
                return self.error_message


class UsernameOrUserIdRequired(ImportValidator):
    error_message = _("One of 'username' or 'user_id' is required")

    def validate_spec(self, spec):
        user_id = spec.get('user_id')
        username = spec.get('username')
        if not user_id and not username:
            return self.error_message


class Duplicates(ImportValidator):
    _error_message = _("'{field}' values must be unique")

    def __init__(self, domain, field, all_specs, check_function=None):
        super().__init__(domain)
        self.field = field
        self.check_function = check_function
        self.duplicates = find_duplicates(all_specs, field)

    @property
    def error_message(self):
        return self._error_message.format(field=self.field)

    def validate_spec(self, row_spec):
        item = row_spec.get(self.field)
        if not item:
            return

        if self.check_function and not self.check_function(item):
            return

        if item in self.duplicates:
            return self.error_message


def find_duplicates(specs, field):
    counter = Counter([
        spec.get(field) for spec in specs
    ])
    return {
        value for value, count in counter.items() if count > 1
    }
