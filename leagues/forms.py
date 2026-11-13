from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from core.choices import Division, SkillTier, Surface, TeamSize, Weekday
from core.forms import TailwindFormMixin

from .models import (
    DIVISIONS_WITH_WOMEN_MINIMUM,
    League,
    Organizer,
    valid_timezones,
)
from .services import EDITABLE_LEAGUE_FIELDS, league_cities

RADIO_ATTRS = {"class": "size-4 shrink-0 accent-court"}


def _any(label, choices):
    return [("", label), *choices]


class LeagueFilterForm(TailwindFormMixin, forms.Form):
    """The league finder's filters. Every field is optional; invalid values are
    simply ignored."""

    weekday = forms.TypedChoiceField(
        label="Night",
        required=False,
        coerce=int,
        empty_value=None,
        choices=_any("Any night", Weekday.choices),
    )
    city = forms.ChoiceField(label="City", required=False)
    team_size = forms.TypedChoiceField(
        label="Team size",
        required=False,
        coerce=int,
        empty_value=None,
        choices=_any("Any size", TeamSize.choices),
    )
    division = forms.ChoiceField(
        label="Division",
        required=False,
        choices=_any("Any division", Division.choices),
    )
    tier = forms.TypedChoiceField(
        label="Level",
        required=False,
        coerce=int,
        empty_value=None,
        choices=_any("Any level", SkillTier.choices),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].choices = _any(
            "Any city", [(city, city) for city in league_cities()]
        )

    def filters(self):
        """The valid filters as keyword arguments for search_leagues()."""
        if not self.is_bound:
            return {}
        self.is_valid()  # Builds cleaned_data from the valid fields only.
        return {
            name: value
            for name, value in self.cleaned_data.items()
            if value not in (None, "")
        }


class LeagueForm(TailwindFormMixin, forms.ModelForm):
    """Add or edit a league. The organizer is chosen with the HTMX organizer
    picker, which fills the hidden ``organizer`` input. Saved through
    create_league() / update_league()."""

    organizer = forms.ModelChoiceField(
        queryset=Organizer.objects.all(),
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = League
        fields = sorted(EDITABLE_LEAGUE_FIELDS)
        labels = {
            "name": "League name",
            "venue_name": "Venue",
            "address": "Address",
            "timezone": "Time zone",
            "weekday": "Night",
            "start_time": "First game starts",
            "game_duration_min": "Game length (minutes)",
            "matches_per_night": "Matches per night",
            "tier": "Level",
            "team_size": "Team size",
            "min_women_on_court": "Minimum women on court",
            "subs_must_be_registered": "Subs must be registered with the organizer",
        }
        help_texts = {
            "address": "Optional.",
            "matches_per_night": "How many games each team plays in a night.",
            "subs_must_be_registered": (
                "Only for leagues with an organizer. Players declare their "
                "registrations on their profile."
            ),
        }
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "tier": forms.RadioSelect(attrs=RADIO_ATTRS),
            "team_size": forms.RadioSelect(attrs=RADIO_ATTRS),
            "division": forms.RadioSelect(attrs={**RADIO_ATTRS, "x-model": "division"}),
            "surface": forms.RadioSelect(attrs=RADIO_ATTRS),
            "subs_must_be_registered": forms.CheckboxInput(attrs=RADIO_ATTRS),
        }

    # For the form's Alpine state: which divisions show the women minimum.
    women_minimum_divisions = [d.value for d in DIVISIONS_WITH_WOMEN_MINIMUM]

    # Field order on the page (Meta.fields is sorted, so set it here).
    field_order = [
        "name",
        "organizer",
        "subs_must_be_registered",
        "weekday",
        "start_time",
        "game_duration_min",
        "matches_per_night",
        "venue_name",
        "address",
        "city",
        "timezone",
        "team_size",
        "division",
        "min_women_on_court",
        "surface",
        "tier",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UUID primary keys exist before saving, so check _state.adding.
        if self.instance._state.adding and not self.initial.get("city"):
            # form.initial (copied from the empty instance) wins over a field's
            # own initial, so set the default there.
            self.initial["city"] = settings.DEFAULT_LEAGUE_CITY
        self.fields["timezone"] = forms.ChoiceField(
            label="Time zone",
            choices=[(tz, tz.replace("_", " ")) for tz in sorted(valid_timezones())],
            initial=settings.DEFAULT_LEAGUE_TIMEZONE,
        )
        self.fields["weekday"].choices = _any("Choose a night", Weekday.choices)
        # Radio groups list only real options (no "---------" blank choice).
        self.fields["tier"].choices = SkillTier.choices
        self.fields["team_size"].choices = TeamSize.choices
        self.fields["division"].choices = Division.choices
        self.fields["surface"].choices = Surface.choices
        for name in ("game_duration_min", "matches_per_night", "min_women_on_court"):
            self.fields[name].widget.attrs["inputmode"] = "numeric"
        # Hidden (and not submitted) unless the division sets a women minimum.
        self.fields["min_women_on_court"].widget.attrs[
            "x-bind:disabled"
        ] = "!needsMinimum"
        self.order_fields(self.field_order)

    def clean(self):
        cleaned = super().clean()
        # A division without a women minimum ignores any value left over from
        # an earlier choice, rather than failing on a hidden field.
        if cleaned.get("division") not in DIVISIONS_WITH_WOMEN_MINIMUM:
            cleaned["min_women_on_court"] = None
        return cleaned

    def league_fields(self):
        return {name: self.cleaned_data[name] for name in EDITABLE_LEAGUE_FIELDS}

    def add_service_errors(self, exc):
        """Show a ValidationError from the service on this form."""
        if hasattr(exc, "error_dict"):
            for field, errors in exc.message_dict.items():
                self.add_error(field if field in self.fields else None, errors)
        else:
            self.add_error(None, exc)


def picked_organizer(form):
    """The organizer currently chosen on a bound or unbound LeagueForm."""
    value = form["organizer"].value()
    if isinstance(value, Organizer):
        return value
    if not value:
        return None
    try:
        return Organizer.objects.filter(pk=value).first()
    except (ValueError, ValidationError):
        return None
