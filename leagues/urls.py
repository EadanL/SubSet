from django.urls import path

from . import views

app_name = "leagues"

urlpatterns = [
    path("", views.LeagueListView.as_view(), name="list"),
    path("new/", views.LeagueCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.LeagueDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", views.LeagueUpdateView.as_view(), name="edit"),
    path(
        "organizers/search/",
        views.OrganizerSearchView.as_view(),
        name="organizer_search",
    ),
    path("organizers/pick/", views.OrganizerPickView.as_view(), name="organizer_pick"),
    path(
        "organizers/new/", views.OrganizerCreateView.as_view(), name="organizer_create"
    ),
    path(
        "registrations/add/",
        views.RegistrationAddView.as_view(),
        name="registration_add",
    ),
    path(
        "registrations/<uuid:organizer_id>/remove/",
        views.RegistrationRemoveView.as_view(),
        name="registration_remove",
    ),
]
