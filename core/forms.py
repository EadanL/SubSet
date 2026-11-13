from django import forms

# Shared input styling built from the design tokens (phase_2b_spec.md §3).
# Focus shows a court-green border (the 3:1 indicator) plus a soft glow;
# outline-hidden keeps an outline in Windows high-contrast mode.
INPUT_CLASSES = (
    "block min-h-12 w-full rounded-lg border border-field bg-surface px-4 py-2.5 "
    "text-ink placeholder:text-slate "
    "transition-colors motion-reduce:transition-none hover:border-ink "
    "focus-visible:border-court focus-visible:outline-hidden "
    "focus-visible:ring-4 focus-visible:ring-court/15 "
    "aria-invalid:border-danger aria-invalid:focus-visible:ring-danger/15 "
    "disabled:cursor-not-allowed disabled:bg-paper disabled:text-slate"
)

# Room for the eye toggle in partials/_password_field.html, and Edge's built-in
# reveal button hidden so there aren't two.
PASSWORD_INPUT_CLASSES = "pr-12 [&::-ms-reveal]:hidden"

# Number inputs without the browser's small up/down arrows.
NUMBER_INPUT_CLASSES = (
    "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none "
    "[&::-webkit-outer-spin-button]:appearance-none"
)

# Select menus drop the browser arrow; partials/_field.html draws a chevron.
SELECT_CLASSES = "cursor-pointer appearance-none pr-11"

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
                elif isinstance(widget, forms.NumberInput):
                    classes.append(NUMBER_INPUT_CLASSES)
                elif isinstance(widget, forms.Select):
                    classes.append(SELECT_CLASSES)
                widget.attrs["class"] = " ".join(c for c in classes if c)
