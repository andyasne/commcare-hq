import uuid

import jsonobject
from jsonobject.exceptions import BadValueError

from casexml.apps.case.mock import CaseBlock, IndexAttrs


def serialize_case(case):
    """Serializes a case for the V0.6 Case API"""
    # TODO should this happen in form_processor/serializers.py using rest_framework.serializers?
    # Dates at least will need to be standardized
    return {
        "domain": case.domain,
        "@case_id": case.case_id,
        "@case_type": case.type,
        "case_name": case.name,
        "external_id": case.external_id,
        "@owner_id": case.owner_id,
        "date_opened": case.opened_on,
        "last_modified": case.modified_on,
        "server_last_modified": case.server_modified_on,
        "closed": case.closed,
        "date_closed": case.closed_on,
        "properties": case.dynamic_case_properties(),
        "indices": {
            index.identifier: {
                "case_id": index.referenced_id,
                "@case_type": index.referenced_type,
                "@relationship": index.relationship,
            }
            for index in case.indices
        }
    }



def is_simple_dict(d):
    if not isinstance(d, dict) or not all(isinstance(v, str) for v in d.values()):
        raise BadValueError("Case properties must be strings")


class JsonIndex(jsonobject.JsonObject):
    case_id = jsonobject.StringProperty(required=True)
    case_type = jsonobject.StringProperty(name='@case_type', required=True)
    relationship = jsonobject.StringProperty(name='@relationship', required=True,
                                             choices=('child', 'extension'))


class BaseJsonCaseChange(jsonobject.JsonObject):
    case_name = jsonobject.StringProperty(required=True)
    external_id = jsonobject.StringProperty()
    user_id = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty(name='@owner_id', required=True)
    properties = jsonobject.DictProperty(validators=[is_simple_dict], default={})
    indices = jsonobject.DictProperty(JsonIndex)

    _allow_dynamic_properties = False

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    def get_caseblock(self):
        case_id = str(uuid.uuid4()) if self._is_case_creation else self.case_id
        case_type = self.case_type if self._is_case_creation else CaseBlock.undefined
        return CaseBlock(
            case_id=case_id,
            user_id=self.user_id,
            case_type=case_type,
            case_name=self.case_name,
            external_id=self.external_id or CaseBlock.undefined,
            owner_id=self.owner_id,
            create=self._is_case_creation,
            update=dict(self.properties),
            index={
                name: IndexAttrs(index.case_type, index.case_id, index.relationship)
                for name, index in self.indices.items()
            },
        ).as_text()


class JsonCaseCreation(BaseJsonCaseChange):
    case_type = jsonobject.StringProperty(name='@case_type', required=True)
    _is_case_creation = True


class JsonCaseUpdate(BaseJsonCaseChange):
    case_id = jsonobject.StringProperty(required=True)
    _is_case_creation = False
