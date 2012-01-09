from corehq.apps.reports import util
from corehq.apps.reports.custom import ReportField
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import HQUserType
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.datespan import datespan_in_request

datespan_default = datespan_in_request(
            from_param="startdate",
            to_param="enddate",
            default_days=7,
        )

class GroupField(ReportField):
    slug = "group"
    template = "reports/partials/fields/select_group.html"

    def update_context(self):
        group = self.request.GET.get('group', '')
        groups = Group.by_domain(self.domain)
        if group:
            group = Group.get(group)
        self.context['group'] = group
        self.context['groups'] = groups

class FilterUsersField(ReportField):
    slug = "ufilter"
    template = "reports/partials/fields/filter_users.html"

    def update_context(self):
        toggle, show_filter = self.get_user_filter(self.request)
        self.context['show_user_filter'] = show_filter
        self.context['toggle_users'] = toggle

    @classmethod
    def get_user_filter(cls, request):
        ufilter = group = individual = None
        try:
            ufilter = request.GET.getlist('ufilter')
            group = request.GET.get('group', '')
            individual = request.GET.get('individual', '')
        except KeyError:
            pass
        show_filter = True
        toggle = HQUserType.use_defaults()
        if ufilter and not (group or individual):
            toggle = HQUserType.use_filter(ufilter)
        elif group or individual:
            show_filter = False
        return toggle, show_filter

class CaseTypeField(ReportField):
    slug = "case_type"
    template = "reports/partials/fields/case_type.html"

    def update_context(self):
        individual = self.request.GET.get('individual', '')
        group = self.request.GET.get('group', '')
        user_filter, _ = FilterUsersField.get_user_filter(self.request)
        users = util.get_all_users_by_domain(self.domain, group, individual, user_filter)
        user_ids = [user.user_id for user in users]
        
        case_types = self.get_case_types(self.domain, user_ids)
        case_type = self.request.GET.get('case_type', '')

        open_count, all_count = self.get_case_counts(self.domain, user_ids=user_ids)
        self.context['case_types'] = case_types
        self.context['case_type'] = case_type
        self.context['all_cases_count'] = {'all': all_count, 'open': open_count}

    @classmethod
    def get_case_types(cls, domain, user_ids=None):
        case_types = {}
        key = [domain]
        for r in get_db().view('hqcase/all_cases',
            startkey=key,
            endkey=key + [{}],
            group_level=2
        ).all():
            case_type = r['key'][1]
            if case_type:
                open_count, all_count = cls.get_case_counts(domain, case_type, user_ids)
                case_types[case_type] = {'open': open_count, 'all': all_count}
        return case_types

    @classmethod
    def get_case_counts(cls, domain, case_type=None, user_ids=None):
        """ Returns open count, all count
        """
        user_ids = user_ids or [{}]
        for view_name in ('hqcase/open_cases', 'hqcase/all_cases'):
            def individual_counts():
                for user_id in user_ids:
                    key = [domain, case_type or {}, user_id]
                    try:
                        yield get_db().view(view_name,
                            startkey=key,
                            endkey=key + [{}],
                            group_level=0
                        ).one()['value']
                    except TypeError:
                        yield 0
            yield sum(individual_counts())

class SelectFormField(ReportField):
    slug = "select_form"
    template = "reports/partials/fields/select_form.html"
    select_all = False

    def update_context(self):
        self.context['select_all'] = self.select_all
        self.context['selected_form'] = self.request.GET.get('form','')
        self.context['available_forms'] = util.form_list(self.domain)

class SelectAllFormField(SelectFormField):
    select_all = True

class SelectCHWField(ReportField):
    slug = "select_chw"
    template = "reports/partials/fields/select_chw.html"

    def update_context(self):
        user_filter, _ = FilterUsersField.get_user_filter(self.request)
        individual = self.request.GET.get('individual', '')
        
        self.context['default_option'] = self.get_default_text(user_filter)
        self.context['users'] = util.user_list(self.domain)
        self.context['individual'] = individual

    @classmethod
    def get_default_text(cls, user_filter):
        default = 'All CHWs'
        if user_filter[HQUserType.ADMIN].show or \
           user_filter[HQUserType.DEMO_USER].show or user_filter[HQUserType.UNKNOWN].show:
            default = '%s & Others' % default
        return default

class DatespanField(ReportField):
    slug = "datespan"
    template = "reports/partials/fields/datespan.html"
    datespan = DateSpan.since(7, format="%Y-%m-%d")

    def update_context(self):
        datespan_default(self.request)
        if self.request.datespan.is_valid():
            self.datespan = self.request.datespan
        self.context['datespan'] = self.datespan

