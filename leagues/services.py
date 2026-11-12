from django.core.exceptions import PermissionDenied, ValidationError

from core.choices import VerificationStatus

from .models import (
    DIVISIONS_WITH_WOMEN_MINIMUM,
    League,
    Organizer,
    OrganizerRegistration,
)

# League details a submitter can set. Verification status and created_by are
# deliberately absent: only staff change those, through Django Admin.
EDITABLE_LEAGUE_FIELDS = frozenset(
    {
        "organizer",
        "name",
        "venue_name",
        "city",
        "address",
        "timezone",
        "weekday",
        "start_time",
        "game_duration_min",
        "matches_per_night",
        "tier",
        "team_size",
        "division",
        "surface",
        "min_women_on_court",
        "subs_must_be_registered",
    }
)


def _league_changes(fields, division):
    unknown = set(fields) - EDITABLE_LEAGUE_FIELDS
    if unknown:
        raise TypeError(f"Not editable: {', '.join(sorted(unknown))}")
    changes = dict(fields)
    # A division without a women minimum clears any value left over from a
    # previous choice, rather than failing on a field the form has hidden.
    if division not in DIVISIONS_WITH_WOMEN_MINIMUM:
        changes["min_women_on_court"] = None
    return changes


def create_organizer(*, created_by, name, website=""):
    """Create and return an organizer. Raises ``ValidationError`` for a blank
    name or one that already exists (ignoring case)."""
    organizer = Organizer(created_by=created_by, name=name, website=website)
    organizer.full_clean()
    organizer.save()
    return organizer


def create_league(*, created_by, **fields):
    """Create and return an unverified league submitted by ``created_by``.

    Raises ``ValidationError`` keyed by field, and ``TypeError`` for fields a
    submitter can't set.
    """
    league = League(
        created_by=created_by,
        **_league_changes(fields, fields.get("division")),
    )
    league.full_clean()
    league.save()
    return league


def can_edit_league(user, league):
    """Only the submitter can edit, and only until staff verify the league."""
    return (
        user is not None
        and user.is_authenticated
        and league.created_by_id == user.pk
        and league.verification_status == VerificationStatus.UNVERIFIED
    )


def update_league(league, *, editor, **fields):
    """Apply changes from the league's submitter.

    Raises ``PermissionDenied`` when ``editor`` can't edit (see
    ``can_edit_league``). On ``ValidationError`` the in-memory league is reset
    to its saved state.
    """
    if not can_edit_league(editor, league):
        raise PermissionDenied(
            "Only the person who added this league can edit it, and only until "
            "it's verified."
        )
    changes = _league_changes(fields, fields.get("division", league.division))
    for field, value in changes.items():
        setattr(league, field, value)
    try:
        league.full_clean()
    except ValidationError:
        league.refresh_from_db(fields=list(changes))
        raise
    league.save(update_fields=[*changes, "updated_at"])
    return league


def declare_registration(*, user, organizer):
    """Record that ``user`` is registered with ``organizer``. Safe to repeat.

    Raises ``ValidationError`` for guest accounts.
    """
    if user.is_guest:
        raise ValidationError("Guest accounts can't register with organizers.")
    registration, _ = OrganizerRegistration.objects.get_or_create(
        user=user, organizer=organizer
    )
    return registration


def withdraw_registration(*, user, organizer):
    """Remove the registration if there is one. Returns whether one existed."""
    deleted, _ = OrganizerRegistration.objects.filter(
        user=user, organizer=organizer
    ).delete()
    return bool(deleted)


def can_sub_in(user, league):
    """Whether ``user`` meets ``league``'s registration rule.

    Unrestricted leagues are open to anyone, guests included. A league that
    requires registered subs needs a full account registered with its
    organizer. Removed leagues accept no one. Availability, level and the
    other matching filters are checked elsewhere.
    """
    if league.verification_status == VerificationStatus.REMOVED:
        return False
    if not league.subs_must_be_registered:
        return True
    if user is None or not user.is_authenticated or user.is_guest:
        return False
    return OrganizerRegistration.objects.filter(
        user=user, organizer_id=league.organizer_id
    ).exists()
