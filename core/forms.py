from django import forms

# Shared input styling built from the design tokens (phase_2b_spec.md §3).
INPUT_CLASSES = (
    "block min-h-11 w-full rounded-xs border border-field bg-surface px-3 py-2 "
    "text-ink placeholder:text-slate aria-invalid:border-danger "
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-court"
)

# Room for the eye toggle in partials/_password_field.html, and Edge's built-in
# reveal button hidden so there aren't two.
PASSWORD_INPUT_CLASSES = "pr-11 [&::-ms-reveal]:hidden"

_UNSTYLED_INPUT_TYPES = {"checkbox", "radio", "hidden"}


class TailwindFormMixin:
    """Give every text-like input and select menu the shared field styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            is_text_like = (
                isinstance(widget, forms.widgets.Input)
                and widget.input_type not in _UNSTYLED_INPUT_TYPES
            )
            # Select menus share the input styling; radio and checkbox groups
            # are ChoiceWidgets but not Selects, so they stay unstyled here.
            if is_text_like or isinstance(widget, forms.Select):
                classes = [INPUT_CLASSES, widget.attrs.get("class", "")]
                if isinstance(widget, forms.PasswordInput):
                    classes.append(PASSWORD_INPUT_CLASSES)
                widget.attrs["class"] = " ".join(c for c in classes if c)
