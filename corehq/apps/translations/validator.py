from __future__ import absolute_import
from __future__ import unicode_literals

import ghdiff
from memoized import memoized

from corehq.apps.translations.app_translations.download import get_bulk_app_sheets_by_name
from corehq.apps.translations.app_translations.utils import (
    get_bulk_app_sheet_headers,
    get_unicode_dicts,
    is_form_sheet,
    is_module_sheet,
    is_modules_and_forms_sheet,
)
from corehq.apps.translations.generators import AppTranslationsGenerator

COLUMNS_TO_COMPARE = {
    'module_and_form': ['Type', 'menu_or_form'],
    'module': ['case_property', 'list_or_detail'],
    'form': ['label'],
}
# return from ghdiff in case of no differences
NO_GHDIFF_MESSAGE = ghdiff.diff([], [], css=False)


class UploadedTranslationsValidator(object):
    """
    this compares the excel sheet uploaded with translations with what would be generated
    with current app state and flags any discrepancies found between the two
    """
    def __init__(self, app, uploaded_workbook, lang_to_compare, lang_prefix='default_'):
        self.app = app
        self.uploaded_workbook = uploaded_workbook
        self.headers = None
        self.expected_rows = None
        self.lang_prefix = lang_prefix
        self.lang_cols_to_compare = [self.lang_prefix + self.app.default_language]
        self.default_language_column = self.lang_prefix + self.app.default_language
        if lang_to_compare in app.langs and lang_to_compare != self.app.default_language:
            self.lang_cols_to_compare.append(self.lang_prefix + lang_to_compare)
            target_lang = lang_to_compare
        else:
            target_lang = self.app.default_language
        self.app_translation_generator = AppTranslationsGenerator(
            self.app.domain, self.app.get_id, None, self.app.default_language, target_lang,
            self.lang_prefix)

    def _generate_expected_headers_and_rows(self):
        self.headers = {h[0]: h[1] for h in get_bulk_app_sheet_headers(
            self.app,
            eligible_for_transifex_only=True
        )}
        self.expected_rows = get_bulk_app_sheets_by_name(
            self.app,
            eligible_for_transifex_only=True
        )

    @memoized
    def _get_header_index(self, sheet_name, header):
        for index, _column_name in enumerate(self.headers[sheet_name]):
            if _column_name == header:
                return index

    def _filter_rows(self, for_type, expected_rows, sheet_name):
        if for_type == 'form':
            return self.app_translation_generator.filter_invalid_rows_for_form(
                expected_rows,
                self.app_translation_generator.sheet_name_to_module_or_form_type_and_id[sheet_name].id,
                self._get_header_index(sheet_name, 'label')
            )
        elif for_type == 'module':
            return self.app_translation_generator.filter_invalid_rows_for_module(
                expected_rows,
                self.app_translation_generator.sheet_name_to_module_or_form_type_and_id[sheet_name].id,
                self._get_header_index(sheet_name, 'case_property'),
                self._get_header_index(sheet_name, 'list_or_detail'),
                self._get_header_index(sheet_name, self.default_language_column)
            )
        elif for_type == 'module_and_form':
            return expected_rows
        assert False, "Unexpected type"

    def _compare_sheet(self, sheet_name, uploaded_rows, for_type):
        """
        :param uploaded_rows: dict
        :param for_type: type of sheet, module_and_forms, module, form
        :return: diff generated by ghdiff or None
        """
        columns_to_compare = COLUMNS_TO_COMPARE[for_type] + self.lang_cols_to_compare
        expected_rows = self._filter_rows(for_type, self.expected_rows[sheet_name], sheet_name)

        parsed_expected_rows = []
        parsed_uploaded_rows = []
        for expected_row in expected_rows:
            parsed_expected_rows.append([expected_row[self._get_header_index(sheet_name, column_name)]
                                        for column_name in columns_to_compare])
        for uploaded_row in uploaded_rows:
            parsed_uploaded_rows.append([uploaded_row.get(column_name) for column_name in columns_to_compare])

        expected_rows_as_string = '\n'.join([', '.join(row) for row in parsed_expected_rows])
        uploaded_rows_as_string = '\n'.join([', '.join(row) for row in parsed_uploaded_rows])
        diff = ghdiff.diff(expected_rows_as_string, uploaded_rows_as_string, css=False)
        if diff == NO_GHDIFF_MESSAGE:
            return None
        return diff

    def compare(self):
        msgs = {}
        self._generate_expected_headers_and_rows()
        for sheet in self.uploaded_workbook.worksheets:
            sheet_name = sheet.worksheet.title
            # if sheet is not in the expected rows, ignore it. This can happen if the module/form sheet is excluded
            # from transifex integration
            if sheet_name not in self.expected_rows:
                continue

            rows = get_unicode_dicts(sheet)
            if is_modules_and_forms_sheet(sheet.worksheet.title):
                error_msgs = self._compare_sheet(sheet_name, rows, 'module_and_form')
            elif is_module_sheet(sheet.worksheet.title):
                error_msgs = self._compare_sheet(sheet_name, rows, 'module')
            elif is_form_sheet(sheet.worksheet.title):
                error_msgs = self._compare_sheet(sheet_name, rows, 'form')
            else:
                raise Exception("Got unexpected sheet name %s" % sheet_name)
            if error_msgs:
                msgs[sheet_name] = error_msgs
        return msgs
