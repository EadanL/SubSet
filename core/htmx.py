from django_htmx.http import HttpResponseClientRedirect

_REDIRECT_CODES = {301, 302, 303}


class HtmxFormMixin:
    """Form views that work both as full pages and as HTMX fragments.

    HTMX requests render ``fragment_template_name`` (the form on its own), so an
    invalid submit swaps the form in place. A successful submit's redirect is
    turned into an ``HX-Redirect`` so the browser loads the next page in full.
    Other requests get the full page and a normal redirect.
    """

    fragment_template_name = None

    def get_template_names(self):
        if self.request.htmx and self.fragment_template_name:
            return [self.fragment_template_name]
        return super().get_template_names()

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if request.htmx and response.status_code in _REDIRECT_CODES:
            return HttpResponseClientRedirect(response["Location"])
        return response
