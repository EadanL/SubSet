from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView

from core.htmx import HtmxFormMixin

from .forms import EmailAuthenticationForm, SignupForm


@method_decorator(sensitive_post_parameters("password1", "password2"), name="dispatch")
class SignupView(HtmxFormMixin, FormView):
    form_class = SignupForm
    template_name = "accounts/signup.html"
    fragment_template_name = "accounts/partials/_signup_form.html"
    # Switches to onboarding once that page ships.
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            user = form.register()
        except ValidationError:
            return self.form_invalid(form)
        login(self.request, user)
        messages.success(self.request, "Account created")
        return super().form_valid(form)


class LoginView(HtmxFormMixin, auth_views.LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "accounts/login.html"
    fragment_template_name = "accounts/partials/_login_form.html"
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "Logged out")
        return response
