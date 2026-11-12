from django import template

from core.forms import INPUT_CLASSES

register = template.Library()


@register.simple_tag
def input_classes():
    """The shared input styling, for inputs written directly in templates."""
    return INPUT_CLASSES
