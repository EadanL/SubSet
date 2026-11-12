from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from core.choices import Position

from .models import AccountType, User


def register_full_account(*, email, password, display_name):
    """Create and return a full account.

    Raises ``ValidationError`` for an invalid or already-registered email
    (including one held by a guest account), a blank display name, or a
    password that fails ``AUTH_PASSWORD_VALIDATORS``.
    """
    user = User(
        email=email,
        display_name=(display_name or "").strip(),
        account_type=AccountType.FULL,
    )
    user.set_password(password)
    user.full_clean()
    try:
        password_validation.validate_password(password, user)
    except ValidationError as exc:
        raise ValidationError({"password": exc.error_list})
    user.save()
    return user


def complete_onboarding(
    user,
    *,
    gender,
    skill_tier,
    main_positions,
    sub_positions=(),
    tier_flex_down=0,
    tier_flex_up=0,
    travel_radius_km=None,
    phone="",
    display_name=None,
):
    """Save a full account's profile, making it onboarded.

    Gender, skill tier and at least one main position are required here even
    though the model allows them blank. Positions are de-duplicated and stored
    in Position order. On ``ValidationError`` the in-memory ``user`` is reset to
    its saved state so callers (e.g. ``request.user``) never hold invalid values.
    """
    if user.account_type != AccountType.FULL:
        raise ValidationError("Guest accounts can't complete onboarding.")

    missing = {}
    if not gender:
        missing["gender"] = "Choose a gender option."
    if skill_tier is None:
        missing["skill_tier"] = "Choose your skill tier."
    if not main_positions:
        missing["main_positions"] = "Choose at least one main position."
    if missing:
        raise ValidationError(missing)

    changes = {
        "gender": gender,
        "skill_tier": skill_tier,
        "main_positions": _ordered_positions(main_positions),
        "sub_positions": _ordered_positions(sub_positions),
        "tier_flex_down": tier_flex_down,
        "tier_flex_up": tier_flex_up,
        "travel_radius_km": travel_radius_km,
        "phone": (phone or "").strip(),
    }
    if display_name is not None:
        changes["display_name"] = display_name.strip()

    for field, value in changes.items():
        setattr(user, field, value)
    try:
        user.full_clean()
    except ValidationError:
        user.refresh_from_db(fields=list(changes))
        raise
    user.save(update_fields=[*changes, "updated_at"])
    return user


def _ordered_positions(positions):
    """De-duplicate and sort into Position order; unknown values go last so
    full_clean() still reports them."""
    order = {value: index for index, value in enumerate(Position.values)}
    return sorted(dict.fromkeys(positions), key=lambda p: order.get(p, len(order)))
