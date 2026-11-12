from django import template

from core.choices import Position, SkillTier

register = template.Library()


@register.filter
def sub_range(user):
    """The levels a player will sub at, e.g. "Novice (C) to Advanced (BB)"."""
    if user.skill_tier is None:
        return ""
    low = SkillTier(user.skill_tier - user.tier_flex_down)
    high = SkillTier(user.skill_tier + user.tier_flex_up)
    if low == high:
        return f"{low.label} only"
    return f"{low.label} to {high.label}"


@register.filter
def position_labels(positions):
    """Stored position values as readable text, e.g. "Setter, Libero"."""
    return ", ".join(Position(p).label for p in positions or [] if p in Position)
