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
