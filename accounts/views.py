from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, TemplateView

from core.htmx import HtmxFormMixin

from .forms import (
    EmailAuthenticationForm,
    EmailPasswordResetForm,
    NewPasswordForm,
    ProfileForm,
    SignupForm,
)
from .mixins import OnboardedRequiredMixin
from .models import User


@method_decorator(sensitive_post_parameters("password1", "password2"), name="dispatch")
class SignupView(HtmxFormMixin, FormView):
    form_class = SignupForm
    template_name = "accounts/signup.html"
    fragment_template_name = "accounts/partials/_signup_form.html"
    success_url = reverse_lazy("accounts:onboarding")

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


# Password reset: Django's built-in flow as full pages (no HTMX), pointed at
# this app's namespaced URLs and templates.


class PasswordResetView(auth_views.PasswordResetView):
    form_class = EmailPasswordResetForm
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    form_class = NewPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class ProfileFormMixin:
    """Bind ProfileForm to a fresh copy of the user.

    A ModelForm writes submitted values onto its instance while validating, so
    using a copy keeps ``request.user`` (shown in the nav) free of invalid input.
    """

    form_class = ProfileForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = User.objects.get(pk=self.request.user.pk)
        return kwargs


class OnboardingView(LoginRequiredMixin, ProfileFormMixin, HtmxFormMixin, FormView):
    template_name = "accounts/onboarding.html"
    fragment_template_name = "accounts/partials/_onboarding_form.html"
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_onboarded:
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            form.save_profile()
        except ValidationError:
            return self.form_invalid(form)
        messages.success(self.request, "Profile saved")
        return super().form_valid(form)


class ProfileView(OnboardedRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        registrations = self.request.user.organizer_registrations.select_related(
            "organizer"
        ).order_by("organizer__name")
        return super().get_context_data(
            profile_user=self.request.user, registrations=registrations, **kwargs
        )


class ProfileCardView(OnboardedRequiredMixin, TemplateView):
    """The read-only card on its own, for "Cancel" in the inline edit form."""

    template_name = "accounts/partials/_profile_card.html"

    def get(self, request, *args, **kwargs):
        if not request.htmx:
            return redirect("accounts:profile")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(profile_user=self.request.user, **kwargs)


class ProfileEditView(
    OnboardedRequiredMixin, ProfileFormMixin, HtmxFormMixin, FormView
):
    """Inline edit on the profile page; a full page when JavaScript is off."""

    template_name = "accounts/profile_edit.html"
    fragment_template_name = "accounts/partials/_profile_form.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        try:
            user = form.save_profile()
        except ValidationError:
            return self.form_invalid(form)
        messages.success(self.request, "Profile saved")
        if self.request.htmx:
            # Swap the card back in, with the toast as an out-of-band update.
            return render(
                self.request,
                "accounts/partials/_profile_saved.html",
                {"profile_user": user},
            )
        return super().form_valid(form)
