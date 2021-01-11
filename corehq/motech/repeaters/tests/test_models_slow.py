import random
import string
from collections import namedtuple
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from requests.exceptions import ConnectionError

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.const import (
    RECORD_FAILURE_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.models import (
    FormRepeater,
    RepeaterStub,
    send_request,
)

DOMAIN = ''.join([random.choice(string.ascii_lowercase) for __ in range(20)])


ResponseMock = namedtuple('ResponseMock', 'status_code reason')


class RepeaterFixtureMixin:

    def setUp(self):
        url = 'https://www.example.com/api/'
        conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
        self.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        self.repeater.save()
        self.repeater_stub = RepeaterStub.objects.create(
            domain=DOMAIN,
            repeater_id=self.repeater.get_id,
        )

    def tearDown(self):
        self.repeater_stub.delete()
        self.repeater.delete()


class ServerErrorTests(RepeaterFixtureMixin, TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.instance_id = str(uuid4())
        self.repeat_record = self.repeater_stub.repeat_records.create(
            domain=DOMAIN,
            payload_id=self.instance_id,
            registered_at=timezone.now(),
        )
        self.post_xform()

    def post_xform(self):
        xform = f"""<?xml version='1.0' ?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
      xmlns="https://www.commcarehq.org/test/ServerErrorTests/">
    <foo/>
    <bar/>
    <meta>
        <deviceID>ServerErrorTests</deviceID>
        <timeStart>2011-10-01T15:25:18.404-04</timeStart>
        <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
        <username>admin</username>
        <userID>testy.mctestface</userID>
        <instanceID>{self.instance_id}</instanceID>
    </meta>
</data>
"""
        submit_form_locally(xform, DOMAIN)

    def reget_repeater_stub(self):
        return RepeaterStub.objects.get(pk=self.repeater_stub.pk)

    def test_success_on_200(self):
        resp = ResponseMock(status_code=200, reason='OK')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_SUCCESS_STATE)
            repeater_stub = self.reget_repeater_stub()
            self.assertIsNone(repeater_stub.next_attempt_at)

    def test_no_backoff_on_409(self):
        resp = ResponseMock(status_code=409, reason='Conflict')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater_stub = self.reget_repeater_stub()
            # Trying tomorrow is just as likely to work as in 5 minutes
            self.assertIsNone(repeater_stub.next_attempt_at)

    def test_no_backoff_on_500(self):
        resp = ResponseMock(status_code=500, reason='Internal Server Error')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater_stub = self.reget_repeater_stub()
            self.assertIsNone(repeater_stub.next_attempt_at)

    def test_backoff_on_503(self):
        resp = ResponseMock(status_code=503, reason='Service Unavailable')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater_stub = self.reget_repeater_stub()
            self.assertIsNotNone(repeater_stub.next_attempt_at)

    def test_backoff_on_connection_error(self):
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.side_effect = ConnectionError()

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater_stub = self.reget_repeater_stub()
            self.assertIsNotNone(repeater_stub.next_attempt_at)
