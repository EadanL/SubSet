import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import User
from core.choices import Gender, Position, SkillTier

pytestmark = pytest.mark.django_db

PASSWORD = "c0rrect-Horse-battery"
HTMX = {"HX-Request": "true"}

ONBOARDING_URL = reverse("accounts:onboarding")
PROFILE_URL = reverse("accounts:profile")
PROFILE_CARD_URL = reverse("accounts:profile_card")
PROFILE_EDIT_URL = reverse("accounts:profile_edit")


@pytest.fixture
def new_user():
    return User.objects.create_user(
        "jordan@example.com", PASSWORD, display_name="Jordan"
    )


@pytest.fixture
def onboarded_user():
    return User.objects.create_user(
        "casey@example.com",
        PASSWORD,
        display_name="Casey",
        gender=Gender.WOMAN,
        skill_tier=SkillTier.INTERMEDIATE,
        main_positions=[Position.SETTER, Position.LIBERO],
        tier_flex_down=1,
        tier_flex_up=1,
        travel_radius_km=25,
    )


def profile_data(**overrides):
    return {
        "display_name": "Jordan K",
        "gender": Gender.MAN,
        "skill_tier": str(SkillTier.INTERMEDIATE),
        "main_positions": [Position.SETTER],
        "sub_positions": [],
        "tier_flex_down": "1",
        "tier_flex_up": "1",
        "travel_radius_km": "20",
        "phone": "",
        **overrides,
    }


def assert_fragment(response):
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html
    return html


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class TestOnboardingAccess:
    def test_anonymous_goes_to_login_with_next(self, client):
        response = client.get(ONBOARDING_URL)

        assert response.status_code == 302
        assert (
            response["Location"] == f"{reverse('accounts:login')}?next={ONBOARDING_URL}"
        )

    def test_onboarded_user_goes_to_profile(self, client, onboarded_user):
        client.force_login(onboarded_user)

        response = client.get(ONBOARDING_URL)

        assert response["Location"] == PROFILE_URL

    def test_signup_then_lands_on_onboarding(self, client):
        response = client.post(
            reverse("accounts:signup"),
            {
                "email": "new@example.com",
                "display_name": "New",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
            follow=True,
        )

        assert response.redirect_chain[-1][0] == ONBOARDING_URL
        assert "Set up your profile" in response.content.decode()


class TestOnboardingPage:
    def test_get_renders_sections_and_choices(self, client, new_user):
        client.force_login(new_user)

        html = client.get(ONBOARDING_URL).content.decode()

        for heading in ("About you", "Your level", "Range you'll sub", "Getting there"):
            assert heading in html
        assert html.count('name="skill_tier"') == len(SkillTier.choices)
        assert html.count('name="gender"') == len(Gender.choices)
        assert 'value="Jordan"' in html  # display name prefilled
        assert "get preview()" in html
        assert 'hx-post="/accounts/onboarding/"' in html

    def test_htmx_valid_submit_saves_and_goes_home(self, client, new_user):
        client.force_login(new_user)

        response = client.post(
            ONBOARDING_URL, profile_data(phone=" +1 (555) 010-0199 "), headers=HTMX
        )

        assert response["HX-Redirect"] == reverse("home")
        new_user.refresh_from_db()
        assert new_user.is_onboarded
        assert new_user.display_name == "Jordan K"
        assert new_user.gender == Gender.MAN
        assert new_user.skill_tier == SkillTier.INTERMEDIATE
        assert (new_user.tier_flex_down, new_user.tier_flex_up) == (1, 1)
        assert new_user.travel_radius_km == 20
        assert new_user.phone == "+1 (555) 010-0199"
        assert "Profile saved" in message_texts(response)

    def test_plain_valid_submit_redirects_home(self, client, new_user):
        client.force_login(new_user)

        response = client.post(ONBOARDING_URL, profile_data())

        assert response.status_code == 302
        assert response["Location"] == reverse("home")

    def test_empty_range_fields_mean_zero(self, client, new_user):
        client.force_login(new_user)

        client.post(
            ONBOARDING_URL,
            profile_data(tier_flex_down="", tier_flex_up=""),
            headers=HTMX,
        )

        new_user.refresh_from_db()
        assert (new_user.tier_flex_down, new_user.tier_flex_up) == (0, 0)
        assert new_user.is_onboarded

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"gender": ""}, "This field is required."),
            ({"skill_tier": ""}, "This field is required."),
            ({"gender": "robot"}, "Select a valid choice."),
            ({"display_name": "J"}, "at least 2 characters"),
            (
                {"skill_tier": str(SkillTier.BEGINNER), "tier_flex_down": "1"},
                "From Beginner you can go at most 0 tier(s) down.",
            ),
            (
                {"skill_tier": str(SkillTier.ELITE), "tier_flex_up": "2"},
                "From Elite (A/AA) you can go at most 0 tier(s) up.",
            ),
            ({"travel_radius_km": "0"}, "greater than or equal to 1"),
            ({"travel_radius_km": "251"}, "less than or equal to 250"),
            ({"phone": "12345"}, "7 to 15 digits"),
            ({"phone": "555-CALL-NOW"}, "7 to 15 digits"),
        ],
    )
    def test_invalid_input_rerenders_fragment_and_saves_nothing(
        self, client, new_user, overrides, expected
    ):
        client.force_login(new_user)

        response = client.post(ONBOARDING_URL, profile_data(**overrides), headers=HTMX)

        html = assert_fragment(response)
        assert expected in html
        new_user.refresh_from_db()
        assert not new_user.is_onboarded
        assert new_user.display_name == "Jordan"

    def test_invalid_submit_keeps_request_user_clean(self, client, new_user):
        client.force_login(new_user)

        response = client.post(
            ONBOARDING_URL,
            profile_data(display_name="Changed", skill_tier="", gender=Gender.WOMAN),
            headers=HTMX,
        )

        # The form was bound to a copy, so the logged-in user object is untouched.
        assert response.wsgi_request.user.display_name == "Jordan"
        assert response.wsgi_request.user.gender == ""


class TestProfileAccess:
    @pytest.mark.parametrize("url", [PROFILE_URL, PROFILE_CARD_URL, PROFILE_EDIT_URL])
    def test_anonymous_goes_to_login(self, client, url):
        response = client.get(url)

        assert response["Location"].startswith(reverse("accounts:login"))

    @pytest.mark.parametrize("url", [PROFILE_URL, PROFILE_CARD_URL, PROFILE_EDIT_URL])
    def test_not_onboarded_goes_to_onboarding(self, client, new_user, url):
        client.force_login(new_user)

        response = client.get(url)

        assert response["Location"] == ONBOARDING_URL


class TestProfilePage:
    def test_shows_saved_profile(self, client, onboarded_user):
        client.force_login(onboarded_user)

        html = client.get(PROFILE_URL).content.decode()

        assert 'id="profile-card"' in html
        assert "Casey" in html
        assert "casey@example.com" in html
        assert "Woman" in html
        assert "Intermediate (B)" in html
        assert "Novice (C) to Advanced (BB)" in html
        assert "25</span> km" in html
        assert "Not set" in html  # phone
        assert f'hx-get="{PROFILE_EDIT_URL}"' in html

    def test_range_without_flex_reads_level_only(self, client, onboarded_user):
        onboarded_user.tier_flex_down = onboarded_user.tier_flex_up = 0
        onboarded_user.save()
        client.force_login(onboarded_user)

        html = client.get(PROFILE_URL).content.decode()

        assert "Intermediate (B) only" in html

    def test_card_fragment_for_cancel(self, client, onboarded_user):
        client.force_login(onboarded_user)

        html = assert_fragment(client.get(PROFILE_CARD_URL, headers=HTMX))

        assert html.lstrip().startswith('<div id="profile-card"')

    def test_card_url_without_htmx_goes_to_profile(self, client, onboarded_user):
        client.force_login(onboarded_user)

        assert client.get(PROFILE_CARD_URL)["Location"] == PROFILE_URL


class TestProfileEdit:
    def test_htmx_get_returns_form_in_place_of_card(self, client, onboarded_user):
        client.force_login(onboarded_user)

        html = assert_fragment(client.get(PROFILE_EDIT_URL, headers=HTMX))

        assert '<form id="profile-card"' in html
        assert 'value="Casey"' in html
        assert f'hx-get="{PROFILE_CARD_URL}"' in html  # Cancel

    def test_plain_get_renders_full_edit_page(self, client, onboarded_user):
        client.force_login(onboarded_user)

        html = client.get(PROFILE_EDIT_URL).content.decode()

        assert "<html" in html
        assert "Edit profile" in html

    def test_htmx_valid_save_returns_card_and_toast(self, client, onboarded_user):
        client.force_login(onboarded_user)

        response = client.post(
            PROFILE_EDIT_URL,
            profile_data(display_name="Casey R", gender=Gender.WOMAN, phone=""),
            headers=HTMX,
        )

        html = assert_fragment(response)
        assert html.lstrip().startswith('<div id="profile-card"')
        assert "Casey R" in html
        assert 'id="messages" aria-live="polite" hx-swap-oob="true"' in html
        assert "Profile saved" in html
        onboarded_user.refresh_from_db()
        assert onboarded_user.display_name == "Casey R"

    def test_htmx_invalid_save_returns_form_with_errors(self, client, onboarded_user):
        client.force_login(onboarded_user)

        response = client.post(
            PROFILE_EDIT_URL,
            profile_data(skill_tier=str(SkillTier.BEGINNER), tier_flex_down="2"),
            headers=HTMX,
        )

        html = assert_fragment(response)
        assert '<form id="profile-card"' in html
        assert "From Beginner you can go at most 0 tier(s) down." in html
        onboarded_user.refresh_from_db()
        assert onboarded_user.skill_tier == SkillTier.INTERMEDIATE

    def test_plain_valid_save_redirects_to_profile(self, client, onboarded_user):
        client.force_login(onboarded_user)

        response = client.post(PROFILE_EDIT_URL, profile_data(gender=Gender.WOMAN))

        assert response.status_code == 302
        assert response["Location"] == PROFILE_URL


class TestPositions:
    def test_onboarding_shows_both_position_groups(self, client, new_user):
        client.force_login(new_user)

        html = client.get(ONBOARDING_URL).content.decode()

        assert "<h2" in html and "Positions</h2>" in html
        assert html.count('name="main_positions"') == len(Position.choices)
        assert html.count('name="sub_positions"') == len(Position.choices)
        assert "All-around" in html
        assert "main.includes($el.value)" in html  # sub disabled when main
        # Main capped at two (">" is HTML-escaped inside the attribute).
        assert "main.length &gt;= 2" in html

    def test_onboarding_saves_positions_in_order(self, client, new_user):
        client.force_login(new_user)

        client.post(
            ONBOARDING_URL,
            profile_data(
                main_positions=[Position.LIBERO, Position.SETTER],
                sub_positions=[Position.ALL_AROUND, Position.OPPOSITE],
            ),
            headers=HTMX,
        )

        new_user.refresh_from_db()
        assert new_user.main_positions == [Position.SETTER, Position.LIBERO]
        assert new_user.sub_positions == [Position.OPPOSITE, Position.ALL_AROUND]
        assert new_user.is_onboarded

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"main_positions": []}, "This field is required."),
            (
                {
                    "main_positions": [
                        Position.SETTER,
                        Position.LIBERO,
                        Position.OPPOSITE,
                    ]
                },
                "Pick at most 2 main positions.",
            ),
            (
                {"main_positions": [Position.SETTER], "sub_positions": ["setter"]},
                "Already one of your main positions: Setter.",
            ),
            ({"sub_positions": ["goalkeeper"]}, "Select a valid choice."),
        ],
    )
    def test_invalid_positions_rerender_with_error(
        self, client, new_user, overrides, expected
    ):
        client.force_login(new_user)

        response = client.post(ONBOARDING_URL, profile_data(**overrides), headers=HTMX)

        html = assert_fragment(response)
        assert expected in html
        new_user.refresh_from_db()
        assert not new_user.is_onboarded

    def test_profile_card_lists_positions(self, client, onboarded_user):
        client.force_login(onboarded_user)

        html = client.get(PROFILE_URL).content.decode()

        assert "Setter, Libero" in html
        assert "Main positions only" in html

    def test_profile_edit_saves_sub_positions(self, client, onboarded_user):
        client.force_login(onboarded_user)

        response = client.post(
            PROFILE_EDIT_URL,
            profile_data(
                gender=Gender.WOMAN,
                main_positions=[Position.SETTER],
                sub_positions=[Position.MIDDLE_BLOCKER],
            ),
            headers=HTMX,
        )

        html = assert_fragment(response)
        assert "Middle blocker" in html
        onboarded_user.refresh_from_db()
        assert onboarded_user.sub_positions == [Position.MIDDLE_BLOCKER]

    def test_existing_profile_without_positions_returns_to_onboarding(
        self, client, onboarded_user
    ):
        User.objects.filter(pk=onboarded_user.pk).update(main_positions=[])
        client.force_login(onboarded_user)

        assert client.get(PROFILE_URL)["Location"] == ONBOARDING_URL
