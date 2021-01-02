import csv
import datetime
import re
import time
from http import HTTPStatus
from inspect import cleandoc
from unittest.mock import Mock

from django.core.management.base import BaseCommand

from corehq.motech.repeaters.const import RECORD_CANCELLED_STATE
from corehq.motech.repeaters.dbaccessors import (
    iter_sql_repeat_records_by_domain,
)
from corehq.motech.repeaters.models import Repeater, SQLRepeatRecord


class Command(BaseCommand):
    help = cleandoc("""
    Perform an action on cancelled repeat records. You may optionally specify a regex to
    filter records using --include or --exclude, and a sleep time with --sleep.
    Specify multiple include or exclude params by space separating them.

    The default action retriggers records. You can specify --action=succeed which will
    call the success callbacks add a new successful attempt to the record
    """)

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument(
            '--action',
            default="retrigger",
            choices=('retrigger', 'succeed'),
            help=("The action to be performed on the repeat records")
        )
        parser.add_argument(
            '--success_message',
            default="Succeeded via management command on {}".format(datetime.date.today()),
            help=("When --action=succeed, the message used in the new successful attempt")
        )
        parser.add_argument(
            '--response_status',
            type=int,
            default=200,
            help=("When --action=succeed, the status code for the mock response")
        )
        parser.add_argument(
            '--include',
            dest='include_regexps',
            nargs='*',
            help=("Regexps that will be applied to a record's 'failure_reason' to "
                  "determine whether to include it."),
        )
        parser.add_argument(
            '--exclude',
            dest='exclude_regexps',
            nargs='*',
            help=("Regexps that will be applied to a record's 'failure_reason' to "
                  "determine whether to exclude it."),
        )
        parser.add_argument(
            '--sleep',
            dest='sleep_time',
            help="Time in seconds to sleep between each request.",
        )
        parser.add_argument(
            '--verbose',
            dest='verbose',
            action='store_true',
            default=False,
            help="Print out all matching failure reasons",
        )

    def handle(self, domain, repeater_id, *args, **options):
        sleep_time = options.get('sleep_time')
        include_regexps = options.get('include_regexps')
        exclude_regexps = options.get('exclude_regexps')
        verbose = options.get('verbose')
        action = options.get('action')
        success_message = options.get('success_message')
        response_status = options.get('response_status')

        repeater = Repeater.get(repeater_id)
        print("Looking up repeat records for '{}'".format(repeater.friendly_name))

        def meets_filter(record):
            if exclude_regexps:  # Match none of the exclude expressions
                if record.failure_reason:
                    if any(re.search(exclude_regex, record.failure_reason)
                           for exclude_regex in exclude_regexps):
                        return False

            if include_regexps:  # Match any of the include expressions
                if not record.failure_reason:
                    return False
                return any(re.search(include_regex, record.failure_reason)
                           for include_regex in include_regexps)
            return True  # No filter applied

        records, __ = iter_sql_repeat_records_by_domain(
            domain, repeater_id, states=[RECORD_CANCELLED_STATE])
        records = list(filter(meets_filter, records))

        if verbose:
            for record in records:
                print(record.payload_id, record.failure_reason)

        total_records = len(records)
        print("Found {} matching records.  {} them?".format(total_records, action))
        if not input("(y/n)") == 'y':
            print("Aborting")
            return

        filename = "{}_{}_records-{}.csv".format(
            action,
            repeater.__class__.__name__,
            datetime.datetime.utcnow().strftime('%Y-%m-%d_%H.%M.%S'))
        with open(filename, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(('record_id', 'payload_id', 'state', 'message'))

            for i, record in enumerate(records):
                try:
                    if action == 'retrigger':
                        record.fire(force_send=True)
                    elif action == 'succeed':
                        self._succeed_record(record, success_message, response_status)
                except Exception as e:
                    print(f"{i + 1}/{total_records}: EXCEPTION {e!r}")
                    writer.writerow((record.pk, record.payload_id, record.state, repr(e)))
                else:
                    print(f"{i + 1}/{total_records}: {record.state}, {record.last_message}")
                    writer.writerow((record.pk, record.payload_id, record.state, record.last_message))
                if sleep_time:
                    time.sleep(float(sleep_time))

        print("Wrote log of changes to {}".format(filename))

    def _succeed_record(
        self,
        record: SQLRepeatRecord,
        success_message: str,
        response_status: int,
    ):
        """
        Treats a SQLRepeatRecord as if it was sent successfully.

        .. note::
           This will call repeater.reset_next_attempt() as if a payload
           was successfully sent.

        """
        try:
            reason = HTTPStatus(response_status).phrase
        except ValueError:
            reason = ''
        response = Mock(
            status_code=response_status,
            reason=reason,
            text=success_message,
        )
        record.add_success_attempt(response)
