from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.core.exceptions import ValidationError

from core.forms import TailwindFormMixin

from .models import User
from .services import register_full_account

PASSWORD_HELP = (
    "At least 8 characters. Avoid common passwords and anything close to your "
    "name or email."
)

# Alpine binding for the eye toggle; `show` lives on the field's wrapper in
# partials/_password_field.html.
SHOW_PASSWORD_ATTRS = {"x-bind:type": "show ? 'text' : 'password'"}

# register_full_account() keys password errors as "password"; this form shows
# them under the confirmation field, as BaseUserCreationForm does.
SERVICE_ERROR_FIELDS = {"password": "password2"}


class SignupForm(TailwindFormMixin, BaseUserCreationForm):
    display_name = forms.CharField(
        label="Display name",
        min_length=2,
        max_length=100,
        help_text="How captains and teammates will see you.",
    )

    class Meta:
        model = User
        fields = ("email", "display_name")
        error_messages = {
            "email": {"unique": "An account with this email already exists."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        email = self.fields["email"]
        email.label = "Email"
        email.required = True
        email.widget.attrs["autocomplete"] = "email"
        self.fields["display_name"].widget.attrs["autocomplete"] = "name"

        password1 = self.fields["password1"]
        password1.label = "Password"
        password1.help_text = PASSWORD_HELP
        password1.widget.attrs.update({**SHOW_PASSWORD_ATTRS, "x-model": "p1"})

        password2 = self.fields["password2"]
        password2.label = "Confirm password"
        password2.help_text = ""
        password2.widget.attrs.update({**SHOW_PASSWORD_ATTRS, "x-model": "p2"})

    def register(self):
        """Create the account through the service.

        Errors the service raises (e.g. an email registered between validation
        and save) are added to this form before re-raising.
        """
        try:
            return register_full_account(
                email=self.cleaned_data["email"],
                password=self.cleaned_data["password1"],
                display_name=self.cleaned_data["display_name"],
            )
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                self.add_error(SERVICE_ERROR_FIELDS.get(field, field), errors)
            raise


class EmailAuthenticationForm(TailwindFormMixin, AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        # One message for every failure, so the form never reveals which
        # emails have accounts.
        "invalid_login": (
            "That email and password don't match an account. Check both and try "
            "again."
        ),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        username = self.fields["username"]
        username.label = "Email"
        username.widget = forms.EmailInput(
            attrs={**username.widget.attrs, "autocomplete": "email"}
        )
        self.fields["password"].widget.attrs.update(SHOW_PASSWORD_ATTRS)


class EmailPasswordResetForm(TailwindFormMixin, PasswordResetForm):
    """Django's reset form already skips inactive users and guests (unusable
    passwords) and matches email case-insensitively."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["autofocus"] = True


class NewPasswordForm(TailwindFormMixin, SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        password1 = self.fields["new_password1"]
        password1.help_text = PASSWORD_HELP
        password1.widget.attrs.update({**SHOW_PASSWORD_ATTRS, "x-model": "p1"})

        password2 = self.fields["new_password2"]
        password2.label = "Confirm new password"
        password2.help_text = ""
        password2.widget.attrs.update({**SHOW_PASSWORD_ATTRS, "x-model": "p2"})
