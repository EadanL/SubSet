import re

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from core.choices import Gender, SkillTier
from core.forms import TailwindFormMixin

from .models import MAX_TIER, MIN_TIER, User
from .services import complete_onboarding, register_full_account

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


PHONE_ALLOWED = re.compile(r"^[0-9 +()\-]+$")
RADIO_ATTRS = {"class": "size-4 shrink-0 accent-court"}


class ProfileForm(TailwindFormMixin, forms.ModelForm):
    """Onboarding and profile edit. Saves through complete_onboarding().

    All three tier fields must stay in this form: User.clean() reports the tier
    range rule on them (see CLAUDE.md, Validation).
    """

    display_name = forms.CharField(label="Display name", min_length=2, max_length=100)
    gender = forms.ChoiceField(
        label="Gender",
        choices=Gender.choices,
        widget=forms.RadioSelect(attrs=RADIO_ATTRS),
        help_text="Used only for leagues with gender rules, such as a minimum "
        "number of women on court.",
    )
    skill_tier = forms.TypedChoiceField(
        label="Your level",
        choices=SkillTier.choices,
        coerce=int,
        widget=forms.RadioSelect(attrs={**RADIO_ATTRS, "x-model.number": "tier"}),
        help_text="Pick the level you usually play at.",
    )
    tier_flex_down = forms.IntegerField(
        label="Levels below yours", required=False, min_value=0
    )
    tier_flex_up = forms.IntegerField(
        label="Levels above yours", required=False, min_value=0
    )
    travel_radius_km = forms.IntegerField(
        label="How far you'll travel (km)",
        required=False,
        validators=[MinValueValidator(1), MaxValueValidator(250)],
        help_text="Optional. Between 1 and 250 km.",
    )
    phone = forms.CharField(
        label="Phone",
        required=False,
        max_length=32,
        help_text="Optional. For captains to text you about a game.",
    )

    class Meta:
        model = User
        fields = (
            "display_name",
            "gender",
            "skill_tier",
            "tier_flex_down",
            "tier_flex_up",
            "travel_radius_km",
            "phone",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].widget.attrs["autocomplete"] = "name"
        for name, model in (("tier_flex_down", "down"), ("tier_flex_up", "up")):
            self.fields[name].widget.attrs.update(
                {"inputmode": "numeric", "x-model.number": model}
            )
        # Limit each range input to what stays on the SkillTier scale.
        self.fields["tier_flex_down"].widget.attrs[
            "x-bind:max"
        ] = f"tier ? tier - {MIN_TIER} : 0"
        self.fields["tier_flex_up"].widget.attrs[
            "x-bind:max"
        ] = f"tier ? {MAX_TIER} - tier : 0"
        self.fields["travel_radius_km"].widget.attrs["inputmode"] = "numeric"
        self.fields["phone"].widget = forms.TextInput(
            attrs={
                **self.fields["phone"].widget.attrs,
                "type": "tel",
                "autocomplete": "tel",
            }
        )

    def clean_tier_flex_down(self):
        return self.cleaned_data["tier_flex_down"] or 0

    def clean_tier_flex_up(self):
        return self.cleaned_data["tier_flex_up"] or 0

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        if not PHONE_ALLOWED.match(phone) or not 7 <= len(digits) <= 15:
            raise ValidationError(
                "Enter a phone number with 7 to 15 digits. You can use spaces, "
                "+, - and brackets."
            )
        return phone

    def save_profile(self):
        """Save through the service, adding any service errors to this form."""
        try:
            return complete_onboarding(self.instance, **self.cleaned_data)
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field, errors in exc.message_dict.items():
                    self.add_error(field if field in self.fields else None, errors)
            else:
                self.add_error(None, exc)
            raise
