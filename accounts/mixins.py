from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class OnboardedRequiredMixin(LoginRequiredMixin):
    """Logged-in users who haven't set up their profile go to onboarding."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_onboarded:
            return redirect("accounts:onboarding")
        return super().dispatch(request, *args, **kwargs)
