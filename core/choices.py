from django.db import models


class SkillTier(models.IntegerChoices):
    """Shared skill scale for players and leagues.

    Integers so a player's tier flex range is simple arithmetic:
    eligible tiers are ``tier - tier_flex_down`` to ``tier + tier_flex_up``.
    """

    BEGINNER = 1, "Beginner"
    NOVICE = 2, "Novice (C)"
    INTERMEDIATE = 3, "Intermediate (B)"
    ADVANCED = 4, "Advanced (BB)"
    ELITE = 5, "Elite (A/AA)"


class Gender(models.TextChoices):
    """Self-reported gender.

    Only ``WOMAN`` satisfies a league's "minimum women on court" rule;
    every other value (including blank) does not.
    """

    WOMAN = "woman", "Woman"
    MAN = "man", "Man"
    NON_BINARY = "non_binary", "Non-binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"


class Position(models.TextChoices):
    """Court positions. ``ALL_AROUND`` covers small-sided formats (4s, beach
    doubles) where fixed positions don't apply."""

    SETTER = "setter", "Setter"
    OUTSIDE_HITTER = "outside_hitter", "Outside hitter"
    OPPOSITE = "opposite", "Opposite"
    MIDDLE_BLOCKER = "middle_blocker", "Middle blocker"
    LIBERO = "libero", "Libero"
    ALL_AROUND = "all_around", "All-around"


class Weekday(models.IntegerChoices):
    """Night of the week. 0 = Monday, matching Python's ``date.weekday()``."""

    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


class TeamSize(models.IntegerChoices):
    """Players per side on court."""

    DOUBLES = 2, "2s"
    TRIPLES = 3, "3s"
    FOURS = 4, "4s"
    SIXES = 6, "6s"


class Division(models.TextChoices):
    """Who a league is for. Co-ed and reverse co-ed leagues set a minimum
    number of women on court; the others don't."""

    COED = "coed", "Co-ed"
    REVERSE_COED = "reverse_coed", "Reverse co-ed"
    MENS = "mens", "Men's"
    WOMENS = "womens", "Women's"
    OPEN = "open", "Open"


class Surface(models.TextChoices):
    INDOOR = "indoor", "Indoor"
    SAND = "sand", "Sand"
    GRASS = "grass", "Grass"


class VerificationStatus(models.TextChoices):
    """Whether a user-submitted record is confirmed to be real.

    New records are visible straight away as ``UNVERIFIED``; staff mark them
    ``VERIFIED``, or ``REMOVED`` (made up or a duplicate), which hides them.
    """

    UNVERIFIED = "unverified", "Unverified"
    VERIFIED = "verified", "Verified"
    REMOVED = "removed", "Removed"
