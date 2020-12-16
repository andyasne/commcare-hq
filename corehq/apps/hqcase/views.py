from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from soil import DownloadBase

from corehq.apps.domain.decorators import (
    api_auth,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqcase.tasks import (
    delete_exploded_case_task,
    explode_case_task,
)
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.form_processor.utils import should_use_sql_backend


class ExplodeCasesView(BaseProjectSettingsView, TemplateView):
    url_name = "explode_cases"
    template_name = "hqcase/explode_cases.html"
    page_title = "Explode Cases"

    @method_decorator(require_superuser_or_contractor)
    def dispatch(self, *args, **kwargs):
        return super(ExplodeCasesView, self).dispatch(*args, **kwargs)

    def get(self, request, domain):
        if not should_use_sql_backend(domain):
            raise Http404("Domain: {} is not a SQL domain".format(domain))
        return super(ExplodeCasesView, self).get(request, domain)

    def get_context_data(self, **kwargs):
        context = super(ExplodeCasesView, self).get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
        })
        return context

    def post(self, request, domain):
        if 'explosion_id' in request.POST:
            return self.delete_cases(request, domain)
        else:
            return self.explode_cases(request, domain)

    def explode_cases(self, request, domain):
        user_id = request.POST.get('user_id')
        factor = request.POST.get('factor', '2')
        try:
            factor = int(factor)
        except ValueError:
            messages.error(request, 'factor must be an int; was: %s' % factor)
        else:
            download = DownloadBase()
            res = explode_case_task.delay(self.domain, user_id, factor)
            download.set_task(res)

            return redirect('hq_soil_download', self.domain, download.download_id)

    def delete_cases(self, request, domain):
        explosion_id = request.POST.get('explosion_id')
        download = DownloadBase()
        res = delete_exploded_case_task.delay(self.domain, explosion_id)
        download.set_task(res)
        return redirect('hq_soil_download', self.domain, download.download_id)


# TODO switch to @require_can_edit_data
@waf_allow('XSS_BODY')
@csrf_exempt
@require_POST
@api_auth
@require_superuser_or_contractor
def create_case(request, domain):
    return JsonResponse({})


@waf_allow('XSS_BODY')
@csrf_exempt
@require_POST
@api_auth
@require_superuser_or_contractor
def update_case(request, domain, case_id):
    return JsonResponse({})


@waf_allow('XSS_BODY')
@csrf_exempt
@require_POST
@api_auth
@require_superuser_or_contractor
def bulk_update_cases(request, domain):
    return JsonResponse({})
