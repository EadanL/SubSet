from functools import lru_cache
from zoneinfo import available_timezones

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from core.choices import (
    Division,
    SkillTier,
    Surface,
    TeamSize,
    VerificationStatus,
    Weekday,
)
from core.models import TimeStampedModel, UUIDModel

# Divisions that set a minimum number of women on court.
DIVISIONS_WITH_WOMEN_MINIMUM = (Division.COED, Division.REVERSE_COED)

GAME_DURATION_MIN, GAME_DURATION_MAX = 10, 240
MATCHES_PER_NIGHT_MIN, MATCHES_PER_NIGHT_MAX = 1, 10


@lru_cache(maxsize=1)
def valid_timezones():
    return frozenset(available_timezones())


def default_league_timezone():
    return settings.DEFAULT_LEAGUE_TIMEZONE


def _collapse_whitespace(value):
    return " ".join((value or "").split())


class Organizer(UUIDModel, TimeStampedModel):
    """Runs one or more leagues and holds player registrations."""

    name = models.CharField(max_length=120)
    website = models.URLField(blank=True)
    # Who submitted it, for moderation only; it grants no rights.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizers_submitted",
    )

    class Meta:
        ordering = [Lower("name")]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="leagues_organizer_name_ci_unique",
                violation_error_message="An organizer with this name already exists.",
            ),
            models.CheckConstraint(
                condition=~Q(name=""), name="leagues_organizer_name_not_blank"
            ),
        ]

    def __str__(self):
        return self.name

    def clean_fields(self, exclude=None):
        self.name = _collapse_whitespace(self.name)
        super().clean_fields(exclude=exclude)


class LeagueQuerySet(models.QuerySet):
    def visible(self):
        """Everything except leagues staff have removed."""
        return self.exclude(verification_status=VerificationStatus.REMOVED)


class League(UUIDModel, TimeStampedModel):
    """A recurring league night. No one owns a league: ``created_by`` records
    who submitted it, and only staff change it once it's verified."""

    organizer = models.ForeignKey(
        Organizer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="leagues",
    )
    name = models.CharField(max_length=120)
    venue_name = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=200, blank=True)
    timezone = models.CharField(max_length=64, default=default_league_timezone)
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    game_duration_min = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(GAME_DURATION_MIN),
            MaxValueValidator(GAME_DURATION_MAX),
        ]
    )
    matches_per_night = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(MATCHES_PER_NIGHT_MIN),
            MaxValueValidator(MATCHES_PER_NIGHT_MAX),
        ],
    )
    tier = models.PositiveSmallIntegerField(choices=SkillTier.choices)
    team_size = models.PositiveSmallIntegerField(choices=TeamSize.choices)
    division = models.CharField(max_length=20, choices=Division.choices)
    surface = models.CharField(
        max_length=10, choices=Surface.choices, default=Surface.INDOOR
    )
    # Required for co-ed and reverse co-ed, empty for every other division.
    min_women_on_court = models.PositiveSmallIntegerField(null=True, blank=True)
    subs_must_be_registered = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=12,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leagues_submitted",
    )

    objects = LeagueQuerySet.as_manager()

    class Meta:
        ordering = ["weekday", "start_time", Lower("name")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(name="") & ~Q(venue_name="") & ~Q(city=""),
                name="leagues_league_text_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(weekday__in=Weekday.values)
                & Q(tier__in=SkillTier.values)
                & Q(team_size__in=TeamSize.values)
                & Q(division__in=Division.values)
                & Q(surface__in=Surface.values)
                & Q(verification_status__in=VerificationStatus.values),
                name="leagues_league_choices_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    game_duration_min__gte=GAME_DURATION_MIN,
                    game_duration_min__lte=GAME_DURATION_MAX,
                    matches_per_night__gte=MATCHES_PER_NIGHT_MIN,
                    matches_per_night__lte=MATCHES_PER_NIGHT_MAX,
                ),
                name="leagues_league_night_lengths_in_range",
            ),
            # Database backstop for the women-minimum rule in clean().
            models.CheckConstraint(
                condition=Q(
                    division__in=DIVISIONS_WITH_WOMEN_MINIMUM,
                    # Explicit: NULL comparisons are unknown, which CHECK passes.
                    min_women_on_court__isnull=False,
                    min_women_on_court__gte=1,
                    min_women_on_court__lte=F("team_size"),
                )
                | (
                    ~Q(division__in=DIVISIONS_WITH_WOMEN_MINIMUM)
                    & Q(min_women_on_court__isnull=True)
                ),
                name="leagues_league_women_minimum_matches_division",
            ),
            models.CheckConstraint(
                condition=Q(subs_must_be_registered=False) | Q(organizer__isnull=False),
                name="leagues_league_registration_needs_organizer",
            ),
            # Exact-duplicate guard. Removed leagues don't block a re-submission.
            models.UniqueConstraint(
                Lower("name"),
                Lower("venue_name"),
                "weekday",
                "start_time",
                condition=~Q(verification_status=VerificationStatus.REMOVED),
                name="leagues_league_no_duplicates",
                violation_error_message=(
                    "A league with this name already plays at this venue on the "
                    "same night and time."
                ),
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def needs_women_minimum(self):
        return self.division in DIVISIONS_WITH_WOMEN_MINIMUM

    def clean_fields(self, exclude=None):
        for field in ("name", "venue_name", "city", "address"):
            setattr(self, field, _collapse_whitespace(getattr(self, field)))
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        # Field-keyed errors make full_clean() skip the matching constraints,
        # so users see these messages rather than generic constraint ones.
        errors = {}
        if self.timezone not in valid_timezones():
            errors["timezone"] = "Choose a valid time zone."
        errors.update(self._women_minimum_errors())
        if self.subs_must_be_registered and self.organizer_id is None:
            errors["subs_must_be_registered"] = (
                "Only leagues with an organizer can require registered subs. "
                "Choose the organizer first."
            )
        if errors:
            raise ValidationError(errors)

    def _women_minimum_errors(self):
        minimum = self.min_women_on_court
        if self.division not in Division.values:
            return {}  # Already reported by clean_fields().
        if not self.needs_women_minimum:
            if minimum is not None:
                return {
                    "min_women_on_court": (
                        "Only co-ed and reverse co-ed leagues set a minimum "
                        "number of women."
                    )
                }
            return {}
        if minimum is None:
            return {
                "min_women_on_court": (
                    f"{Division(self.division).label} leagues need a minimum "
                    "number of women on court."
                )
            }
        if minimum < 1:
            return {"min_women_on_court": "The minimum must be at least 1."}
        if self.team_size in TeamSize.values and minimum > self.team_size:
            return {
                "min_women_on_court": (
                    f"The minimum can't be more than the team size "
                    f"({TeamSize(self.team_size).label})."
                )
            }
        return {}


class OrganizerRegistration(UUIDModel, TimeStampedModel):
    """A player's self-declared registration with an organizer. It makes them
    eligible for all that organizer's registration-only leagues.
    ``created_at`` is when it was declared."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organizer_registrations",
    )
    organizer = models.ForeignKey(
        Organizer, on_delete=models.CASCADE, related_name="registrations"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organizer"],
                name="leagues_registration_unique_per_organizer",
            ),
        ]

    def __str__(self):
        return f"{self.user} with {self.organizer}"

    def clean(self):
        super().clean()
        if self.user_id and self.user.is_guest:
            raise ValidationError(
                {"user": "Guest accounts can't register with organizers."}
            )
