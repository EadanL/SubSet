from django.contrib import admin, messages

from core.choices import VerificationStatus

from .models import League, Organizer, OrganizerRegistration


@admin.register(Organizer)
class OrganizerAdmin(admin.ModelAdmin):
    list_display = ("name", "website", "created_by", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_by", "created_at", "updated_at")


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    """Staff verify leagues here and make any changes once one is verified."""

    list_display = (
        "name",
        "organizer",
        "city",
        "weekday",
        "start_time",
        "team_size",
        "division",
        "tier",
        "verification_status",
    )
    list_filter = (
        "verification_status",
        "weekday",
        "city",
        "division",
        "team_size",
        "surface",
        "subs_must_be_registered",
    )
    search_fields = ("name", "venue_name", "city", "organizer__name")
    autocomplete_fields = ("organizer",)
    readonly_fields = ("created_by", "created_at", "updated_at")
    actions = ("mark_verified", "mark_removed")

    @admin.action(description="Mark selected leagues as verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(verification_status=VerificationStatus.VERIFIED)
        self.message_user(request, f"{updated} league(s) marked verified.")

    @admin.action(description="Remove selected leagues (made up or duplicate)")
    def mark_removed(self, request, queryset):
        updated = queryset.update(verification_status=VerificationStatus.REMOVED)
        self.message_user(
            request, f"{updated} league(s) removed and hidden.", messages.WARNING
        )


@admin.register(OrganizerRegistration)
class OrganizerRegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "organizer", "created_at")
    list_filter = ("organizer",)
    search_fields = ("user__email", "user__display_name", "organizer__name")
    autocomplete_fields = ("user", "organizer")
