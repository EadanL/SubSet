import datetime

import pytest
from django.urls import reverse

from accounts.models import User
from core.choices import (
    Division,
    Gender,
    Position,
    SkillTier,
    TeamSize,
    VerificationStatus,
    Weekday,
)
from leagues.models import League, Organizer, OrganizerRegistration
from leagues.services import create_league, create_organizer, declare_registration

pytestmark = pytest.mark.django_db

PASSWORD = "c0rrect-Horse-battery"
HTMX = {"HX-Request": "true"}
LIST_URL = reverse("leagues:list")
CREATE_URL = reverse("leagues:create")


def make_user(email, **extra):
    return User.objects.create_user(
        email,
        PASSWORD,
        display_name=email.split("@")[0].title(),
        gender=Gender.WOMAN,
        skill_tier=SkillTier.INTERMEDIATE,
        main_positions=[Position.SETTER],
        **extra,
    )


def league_fields(**overrides):
    return {
        "name": "Tuesday Coed B",
        "venue_name": "Riverside Rec Centre",
        "city": "Calgary",
        "weekday": Weekday.TUESDAY,
        "start_time": datetime.time(19, 40),
        "game_duration_min": 60,
        "matches_per_night": 1,
        "tier": SkillTier.INTERMEDIATE,
        "team_size": TeamSize.SIXES,
        "division": Division.COED,
        "min_women_on_court": 2,
        **overrides,
    }


def form_data(**overrides):
    data = {
        "name": "Thursday Reverse 4s",
        "organizer": "",
        "weekday": str(Weekday.THURSDAY),
        "start_time": "20:15",
        "game_duration_min": "55",
        "matches_per_night": "2",
        "venue_name": "Shaw Centre",
        "address": "",
        "city": "Calgary",
        "timezone": "America/Edmonton",
        "team_size": str(TeamSize.FOURS),
        "division": Division.REVERSE_COED,
        "min_women_on_court": "2",
        "surface": "indoor",
        "tier": str(SkillTier.NOVICE),
    }
    data.update(overrides)
    return data


def assert_fragment(response):
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html
    return html


@pytest.fixture
def player():
    return make_user("jordan@example.com")


@pytest.fixture
def other_player():
    return make_user("casey@example.com")


@pytest.fixture
def organizer(player):
    return create_organizer(created_by=player, name="Northside Rec")


@pytest.fixture
def league(player):
    return create_league(created_by=player, **league_fields())


@pytest.fixture
def restricted_league(player, organizer):
    return create_league(
        created_by=player,
        **league_fields(
            name="Thursday Women's 4s",
            organizer=organizer,
            subs_must_be_registered=True,
            weekday=Weekday.THURSDAY,
            team_size=TeamSize.FOURS,
            division=Division.WOMENS,
            city="Airdrie",
        ),
    )


class TestFinder:
    def test_lists_visible_leagues_with_chips(self, client, league, restricted_league):
        removed = create_league(
            created_by=None, **league_fields(name="Fake League", venue_name="Nowhere")
        )
        League.objects.filter(pk=removed.pk).update(
            verification_status=VerificationStatus.REMOVED
        )

        html = client.get(LIST_URL).content.decode()

        assert "Tuesday Coed B" in html
        assert "Thursday Women&#x27;s 4s" in html
        assert "Fake League" not in html
        assert "Registered subs only" in html
        assert "Unverified" in html
        assert "7:40 pm" in html
        assert 'hx-push-url="true"' in html

    def test_city_filter_lists_cities_with_leagues(
        self, client, league, restricted_league
    ):
        html = client.get(LIST_URL).content.decode()

        assert '<option value="Airdrie">Airdrie</option>' in html
        assert '<option value="Calgary">Calgary</option>' in html

    @pytest.mark.parametrize(
        "params, shown, hidden",
        [
            ({"weekday": Weekday.THURSDAY}, "Women&#x27;s 4s", "Tuesday Coed B"),
            ({"city": "Calgary"}, "Tuesday Coed B", "Women&#x27;s 4s"),
            ({"team_size": TeamSize.FOURS}, "Women&#x27;s 4s", "Tuesday Coed B"),
            ({"division": Division.COED}, "Tuesday Coed B", "Women&#x27;s 4s"),
        ],
    )
    def test_htmx_filter_returns_results_fragment(
        self, client, league, restricted_league, params, shown, hidden
    ):
        response = client.get(LIST_URL, params, headers=HTMX)

        html = assert_fragment(response)
        assert html.lstrip().startswith('<div id="league-results"')
        assert shown in html
        assert hidden not in html
        assert "HX-Request" in response["Vary"]

    def test_history_restore_gets_full_page(self, client, league):
        response = client.get(
            LIST_URL, headers={**HTMX, "HX-History-Restore-Request": "true"}
        )

        assert "<html" in response.content.decode()

    def test_invalid_filter_values_are_ignored(self, client, league):
        html = client.get(LIST_URL, {"weekday": "9", "tier": "x"}).content.decode()

        assert "Tuesday Coed B" in html

    def test_empty_state(self, client):
        html = client.get(LIST_URL).content.decode()

        assert "No leagues match these filters" in html

    def test_add_link_only_for_signed_in(self, client, player):
        assert f'href="{CREATE_URL}"' not in client.get(LIST_URL).content.decode()
        client.force_login(player)
        assert f'href="{CREATE_URL}"' in client.get(LIST_URL).content.decode()


class TestDetail:
    def url(self, league):
        return reverse("leagues:detail", args=[league.pk])

    def test_shows_league_details(self, client, league):
        html = client.get(self.url(league)).content.decode()

        assert "Tuesdays at 7:40 pm" in html
        assert "Riverside Rec Centre" in html
        assert "Independent league" in html
        assert "Minimum women on court" in html
        assert "Open to all subs" in html
        assert "America/Edmonton" in html

    def test_removed_league_is_not_found(self, client, league):
        League.objects.filter(pk=league.pk).update(
            verification_status=VerificationStatus.REMOVED
        )

        assert client.get(self.url(league)).status_code == 404

    def test_restricted_note_for_anonymous(self, client, restricted_league):
        html = client.get(self.url(restricted_league)).content.decode()

        assert "Log in to check your registrations." in html
        assert "Minimum women on court" not in html

    def test_restricted_note_for_unregistered_player(
        self, client, other_player, restricted_league
    ):
        client.force_login(other_player)

        html = client.get(self.url(restricted_league)).content.decode()

        assert "If you're registered with them, add them on" in html

    def test_restricted_note_for_registered_player(
        self, client, other_player, restricted_league
    ):
        declare_registration(user=other_player, organizer=restricted_league.organizer)
        client.force_login(other_player)

        html = client.get(self.url(restricted_league)).content.decode()

        assert "You're registered with Northside Rec" in html

    def test_edit_link_for_submitter_until_verified(self, client, player, league):
        client.force_login(player)
        edit_url = reverse("leagues:edit", args=[league.pk])

        assert edit_url in client.get(self.url(league)).content.decode()

        League.objects.filter(pk=league.pk).update(
            verification_status=VerificationStatus.VERIFIED
        )
        assert edit_url not in client.get(self.url(league)).content.decode()

    def test_no_edit_link_for_other_players(self, client, other_player, league):
        client.force_login(other_player)

        html = client.get(self.url(league)).content.decode()

        assert reverse("leagues:edit", args=[league.pk]) not in html


class TestCreate:
    def test_requires_login(self, client):
        response = client.get(CREATE_URL)

        assert response["Location"].startswith(reverse("accounts:login"))

    def test_form_defaults_to_calgary(self, client, player):
        client.force_login(player)

        html = client.get(CREATE_URL).content.decode()

        assert 'value="Calgary"' in html
        assert '<option value="America/Edmonton" selected>' in html
        assert 'id="organizer-picker"' in html
        assert '"---------"' not in html and ">---------<" not in html

    def test_htmx_valid_submit_creates_unverified_league(self, client, player):
        client.force_login(player)

        response = client.post(CREATE_URL, form_data(), headers=HTMX)

        league = League.objects.get(name="Thursday Reverse 4s")
        assert response["HX-Redirect"] == reverse("leagues:detail", args=[league.pk])
        assert league.created_by == player
        assert league.verification_status == VerificationStatus.UNVERIFIED
        assert league.min_women_on_court == 2
        assert league.start_time == datetime.time(20, 15)

    def test_plain_valid_submit_redirects(self, client, player):
        client.force_login(player)

        response = client.post(CREATE_URL, form_data())

        assert response.status_code == 302

    def test_stale_women_minimum_is_dropped_for_mens(self, client, player):
        client.force_login(player)

        client.post(
            CREATE_URL,
            form_data(division=Division.MENS, min_women_on_court="3"),
            headers=HTMX,
        )

        assert League.objects.get().min_women_on_court is None

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"min_women_on_court": ""}, "Reverse co-ed leagues need a minimum"),
            ({"min_women_on_court": "5"}, "more than the team size (4s)"),
            (
                {"subs_must_be_registered": "on"},
                "Only leagues with an organizer can require registered subs.",
            ),
            ({"game_duration_min": "5"}, "greater than or equal to 10"),
            ({"weekday": ""}, "This field is required."),
            ({"timezone": "Mars/Base"}, "Select a valid choice."),
        ],
    )
    def test_invalid_submit_rerenders_with_error(
        self, client, player, overrides, expected
    ):
        client.force_login(player)

        response = client.post(CREATE_URL, form_data(**overrides), headers=HTMX)

        html = assert_fragment(response)
        assert expected in html
        assert not League.objects.exists()

    def test_duplicate_is_rejected(self, client, player, league):
        client.force_login(player)

        response = client.post(
            CREATE_URL,
            form_data(
                name="tuesday coed b",
                venue_name="Riverside Rec Centre",
                weekday=str(Weekday.TUESDAY),
                start_time="19:40",
            ),
            headers=HTMX,
        )

        assert "already plays at this venue" in assert_fragment(response)

    def test_with_organizer_and_registered_subs(self, client, player, organizer):
        client.force_login(player)

        client.post(
            CREATE_URL,
            form_data(organizer=str(organizer.pk), subs_must_be_registered="on"),
            headers=HTMX,
        )

        league = League.objects.get()
        assert league.organizer == organizer
        assert league.subs_must_be_registered

    def test_error_rerender_keeps_chosen_organizer(self, client, player, organizer):
        client.force_login(player)

        response = client.post(
            CREATE_URL,
            form_data(organizer=str(organizer.pk), name=""),
            headers=HTMX,
        )

        html = assert_fragment(response)
        assert f'name="organizer" value="{organizer.pk}"' in html
        assert "Northside Rec" in html


class TestEdit:
    def url(self, league):
        return reverse("leagues:edit", args=[league.pk])

    def test_submitter_can_edit_while_unverified(self, client, player, league):
        client.force_login(player)

        response = client.post(
            self.url(league),
            form_data(name="Tuesday Coed A", division=Division.COED),
            headers=HTMX,
        )

        assert response["HX-Redirect"] == reverse("leagues:detail", args=[league.pk])
        league.refresh_from_db()
        assert league.name == "Tuesday Coed A"

    def test_form_is_prefilled(self, client, player, league):
        client.force_login(player)

        html = client.get(self.url(league)).content.decode()

        assert 'value="Tuesday Coed B"' in html
        assert 'value="19:40"' in html
        assert "Save league" in html

    def test_other_player_is_forbidden(self, client, other_player, league):
        client.force_login(other_player)

        assert client.get(self.url(league)).status_code == 403

    def test_verified_league_is_forbidden_for_submitter(self, client, player, league):
        League.objects.filter(pk=league.pk).update(
            verification_status=VerificationStatus.VERIFIED
        )
        client.force_login(player)

        assert client.post(self.url(league), form_data()).status_code == 403

    def test_anonymous_goes_to_login(self, client, league):
        assert client.get(self.url(league))["Location"].startswith(
            reverse("accounts:login")
        )


class TestOrganizerPicker:
    search_url = reverse("leagues:organizer_search")
    pick_url = reverse("leagues:organizer_pick")
    new_url = reverse("leagues:organizer_create")

    def test_search_requires_login(self, client):
        assert client.get(self.search_url, {"q": "north"}).status_code == 302

    def test_search_lists_matches_and_offers_to_add(self, client, player, organizer):
        client.force_login(player)

        html = assert_fragment(
            client.get(self.search_url, {"q": "north"}, headers=HTMX)
        )

        assert "Northside Rec" in html
        assert f"?organizer={organizer.pk}" in html
        assert "Add “north” as a new organizer" in html

    def test_exact_match_hides_add_option(self, client, player, organizer):
        client.force_login(player)

        html = client.get(self.search_url, {"q": "northside rec"}).content.decode()

        assert "as a new organizer" not in html

    def test_empty_query_returns_nothing(self, client, player, organizer):
        client.force_login(player)

        assert client.get(self.search_url, {"q": "  "}).content.decode().strip() == ""

    def test_pick_returns_chosen_state(self, client, player, organizer):
        client.force_login(player)

        html = assert_fragment(
            client.get(self.pick_url, {"organizer": organizer.pk}, headers=HTMX)
        )

        assert f'name="organizer" value="{organizer.pk}"' in html
        assert "Change" in html

    @pytest.mark.parametrize("value", ["", "not-a-uuid"])
    def test_pick_without_valid_id_returns_search(self, client, player, value):
        client.force_login(player)

        html = client.get(self.pick_url, {"organizer": value}).content.decode()

        assert 'id="organizer-search"' in html

    def test_add_new_organizer(self, client, player):
        client.force_login(player)

        html = assert_fragment(
            client.post(self.new_url, {"organizer_name": " Southside  Sports "})
        )

        organizer = Organizer.objects.get(name="Southside Sports")
        assert organizer.created_by == player
        assert f'name="organizer" value="{organizer.pk}"' in html

    def test_add_reuses_existing_name(self, client, player, organizer):
        client.force_login(player)

        client.post(self.new_url, {"organizer_name": "NORTHSIDE REC"})

        assert Organizer.objects.count() == 1

    def test_add_blank_name_shows_error(self, client, player):
        client.force_login(player)

        html = client.post(self.new_url, {"organizer_name": "  "}).content.decode()

        assert 'id="organizer-search"' in html
        assert "This field cannot be blank." in html


class TestRegistrationsOnProfile:
    add_url = reverse("leagues:registration_add")

    def remove_url(self, organizer):
        return reverse("leagues:registration_remove", args=[organizer.pk])

    def test_profile_shows_section(self, client, player, organizer):
        declare_registration(user=player, organizer=organizer)
        client.force_login(player)

        html = client.get(reverse("accounts:profile")).content.decode()

        assert 'id="organizer-registrations"' in html
        assert "Northside Rec" in html
        assert '"purpose": "register"' in html

    def test_register_search_leaves_out_existing(self, client, player, organizer):
        create_organizer(created_by=player, name="Northgate Volleyball")
        declare_registration(user=player, organizer=organizer)
        client.force_login(player)

        html = client.get(
            reverse("leagues:organizer_search"), {"q": "north", "purpose": "register"}
        ).content.decode()

        assert "Northgate Volleyball" in html
        assert "Northside Rec" not in html
        assert "as a new organizer" not in html
        assert self.add_url in html

    def test_htmx_add_returns_section(self, client, player, organizer):
        client.force_login(player)

        response = client.post(
            self.add_url, {"organizer": str(organizer.pk)}, headers=HTMX
        )

        html = assert_fragment(response)
        assert html.lstrip().startswith('<section id="organizer-registrations"')
        assert "Northside Rec" in html
        assert OrganizerRegistration.objects.filter(
            user=player, organizer=organizer
        ).exists()

    @pytest.mark.parametrize("value", ["", "not-a-uuid"])
    def test_add_without_organizer_shows_error(self, client, player, value):
        client.force_login(player)

        html = client.post(self.add_url, {"organizer": value}, headers=HTMX)

        assert "Choose an organizer from the list." in html.content.decode()

    def test_htmx_remove_returns_section(self, client, player, organizer):
        declare_registration(user=player, organizer=organizer)
        client.force_login(player)

        html = assert_fragment(client.post(self.remove_url(organizer), headers=HTMX))

        assert "You haven't added any organizers yet." in html
        assert not OrganizerRegistration.objects.exists()

    def test_plain_post_redirects_to_profile(self, client, player, organizer):
        client.force_login(player)

        response = client.post(self.add_url, {"organizer": str(organizer.pk)})

        assert response["Location"] == reverse("accounts:profile")

    def test_get_is_not_allowed(self, client, player, organizer):
        client.force_login(player)

        assert client.get(self.add_url).status_code == 405
        assert client.get(self.remove_url(organizer)).status_code == 405


class TestNav:
    def test_leagues_link_for_everyone(self, client, player):
        assert f'href="{LIST_URL}"' in client.get(reverse("home")).content.decode()
        client.force_login(player)
        assert f'href="{LIST_URL}"' in client.get(reverse("home")).content.decode()
