from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    if request.user.is_authenticated and not request.user.is_onboarded:
        return redirect("accounts:onboarding")
    return render(request, "home.html")
