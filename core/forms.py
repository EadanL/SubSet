from django import forms

# Shared input styling built from the design tokens (phase_2b_spec.md §3).
INPUT_CLASSES = (
    "block min-h-11 w-full rounded-xs border border-field bg-surface px-3 py-2 "
    "text-ink placeholder:text-slate aria-invalid:border-danger "
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-court"
)

_UNSTYLED_INPUT_TYPES = {"checkbox", "radio", "hidden"}


class TailwindFormMixin:
    """Give every text-like input the shared field styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if (
                isinstance(widget, forms.widgets.Input)
                and widget.input_type not in _UNSTYLED_INPUT_TYPES
            ):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{INPUT_CLASSES} {existing}".strip()
