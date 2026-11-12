from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.vary import vary_on_headers
from django.views.generic import DetailView, FormView, ListView

from core.htmx import HtmxFormMixin

from .forms import LeagueFilterForm, LeagueForm, picked_organizer
from .models import League, Organizer
from .services import (
    can_edit_league,
    can_sub_in,
    create_league,
    declare_registration,
    find_or_create_organizer,
    search_leagues,
    search_organizers,
    update_league,
    withdraw_registration,
)


@method_decorator(vary_on_headers("HX-Request"), name="dispatch")
class LeagueListView(ListView):
    """The league finder. Filter changes swap just the results list; an HTMX
    history restore (back button) gets the full page."""

    template_name = "leagues/league_list.html"
    context_object_name = "leagues"

    def get_queryset(self):
        self.filter_form = LeagueFilterForm(self.request.GET or None)
        return search_leagues(**self.filter_form.filters())

    def get_template_names(self):
        htmx = self.request.htmx
        if htmx and not htmx.history_restore_request:
            return ["leagues/partials/_league_results.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        return super().get_context_data(filter_form=self.filter_form, **kwargs)


class LeagueDetailView(DetailView):
    template_name = "leagues/league_detail.html"
    context_object_name = "league"

    def get_queryset(self):
        return League.objects.visible().select_related("organizer")

    def get_context_data(self, **kwargs):
        user, league = self.request.user, self.object
        return super().get_context_data(
            can_edit=can_edit_league(user, league),
            can_sub=can_sub_in(user, league),
            **kwargs,
        )


class LeagueFormViewMixin(LoginRequiredMixin, HtmxFormMixin):
    form_class = LeagueForm
    template_name = "leagues/league_form.html"
    fragment_template_name = "leagues/partials/_league_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organizer"] = picked_organizer(context["form"])
        return context


class LeagueCreateView(LeagueFormViewMixin, FormView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = League(created_by=self.request.user)
        return kwargs

    def form_valid(self, form):
        try:
            self.league = create_league(
                created_by=self.request.user, **form.league_fields()
            )
        except ValidationError as exc:
            form.add_service_errors(exc)
            return self.form_invalid(form)
        messages.success(self.request, "League added")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("leagues:detail", args=[self.league.pk])


class LeagueUpdateView(LeagueFormViewMixin, FormView):
    """Edit by the league's submitter, only while it's unverified."""

    def dispatch(self, request, *args, **kwargs):
        self.league = get_object_or_404(League.objects.visible(), pk=kwargs["pk"])
        if request.user.is_authenticated and not can_edit_league(
            request.user, self.league
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Bind to a fresh copy so invalid input never touches self.league.
        kwargs["instance"] = League.objects.get(pk=self.league.pk)
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(league=self.league, **kwargs)

    def form_valid(self, form):
        try:
            update_league(self.league, editor=self.request.user, **form.league_fields())
        except ValidationError as exc:
            form.add_service_errors(exc)
            return self.form_invalid(form)
        messages.success(self.request, "League saved")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("leagues:detail", args=[self.league.pk])


# Organizer picker (league form) and search (profile registrations). These
# return HTML fragments for HTMX.


def _picker(request, organizer=None, error=""):
    return render(
        request,
        "leagues/partials/_organizer_picker.html",
        {"organizer": organizer, "picker_error": error},
    )


@method_decorator(require_GET, name="dispatch")
class OrganizerSearchView(LoginRequiredMixin, View):
    """Matches for the search box. ``purpose=register`` lists organizers to
    register with (leaving out ones already added); otherwise results pick an
    organizer for the league form and offer to add a new one."""

    def get(self, request):
        query = " ".join(request.GET.get("q", "").split())
        registering = request.GET.get("purpose") == "register"
        organizers = search_organizers(
            query, exclude_registered_by=request.user if registering else None
        )
        exact_match = any(o.name.lower() == query.lower() for o in organizers)
        return render(
            request,
            "leagues/partials/_organizer_results.html",
            {
                "query": query,
                "organizers": organizers,
                "registering": registering,
                "can_add": bool(query) and not registering and not exact_match,
            },
        )


@method_decorator(require_GET, name="dispatch")
class OrganizerPickView(LoginRequiredMixin, View):
    """The picker with ``?organizer=<id>`` chosen, or empty to search again."""

    def get(self, request):
        organizer = None
        if request.GET.get("organizer"):
            try:
                organizer = Organizer.objects.filter(
                    pk=request.GET["organizer"]
                ).first()
            except ValidationError:
                organizer = None
        return _picker(request, organizer)


@method_decorator(require_POST, name="dispatch")
class OrganizerCreateView(LoginRequiredMixin, View):
    """Add a new organizer from the league form (reusing one with the same
    name) and return the picker with it chosen."""

    def post(self, request):
        try:
            organizer = find_or_create_organizer(
                created_by=request.user,
                name=request.POST.get("organizer_name", ""),
            )
        except ValidationError as exc:
            return _picker(request, error=" ".join(exc.messages))
        return _picker(request, organizer)


# Organizer registrations on the profile page.


def _registrations(request, error=""):
    if not request.htmx:
        if error:
            messages.error(request, error)
        return redirect("accounts:profile")
    return render(
        request,
        "leagues/partials/_registrations.html",
        {
            "registrations": request.user.organizer_registrations.select_related(
                "organizer"
            ).order_by("organizer__name"),
            "registration_error": error,
        },
    )


@method_decorator(require_POST, name="dispatch")
class RegistrationAddView(LoginRequiredMixin, View):
    def post(self, request):
        organizer = None
        try:
            organizer = Organizer.objects.filter(
                pk=request.POST.get("organizer")
            ).first()
        except ValidationError:
            pass
        if organizer is None:
            return _registrations(request, "Choose an organizer from the list.")
        try:
            declare_registration(user=request.user, organizer=organizer)
        except ValidationError as exc:
            return _registrations(request, " ".join(exc.messages))
        return _registrations(request)


@method_decorator(require_POST, name="dispatch")
class RegistrationRemoveView(LoginRequiredMixin, View):
    def post(self, request, organizer_id):
        organizer = get_object_or_404(Organizer, pk=organizer_id)
        withdraw_registration(user=request.user, organizer=organizer)
        return _registrations(request)
