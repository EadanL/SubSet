import io

import pytest
from django.core.mail import EmailMessage
from django.urls import reverse

from accounts.models import User
from core.choices import Gender, Position, SkillTier
from core.mail import ReadableConsoleEmailBackend

pytestmark = pytest.mark.django_db


@pytest.fixture
def home_url():
    return reverse("home")


class TestBaseLayout:
    def test_loads_compiled_css_and_vendored_scripts(self, client, home_url):
        html = client.get(home_url).content.decode()

        assert "css/tailwind.css" in html
        assert "vendor/htmx.min.js" in html
        assert "vendor/alpine.min.js" in html

    def test_body_sends_csrf_token_with_htmx_requests(self, client, home_url):
        response = client.get(home_url)
        html = response.content.decode()

        assert 'hx-headers=\'{"X-CSRFToken": "' in html
        assert "csrftoken" in response.cookies

    def test_has_skip_link_and_main_landmark(self, client, home_url):
        html = client.get(home_url).content.decode()

        assert 'href="#main"' in html
        assert '<main id="main"' in html

    def test_renders_messages_container(self, client, home_url):
        html = client.get(home_url).content.decode()

        assert 'id="messages"' in html


class TestHome:
    def test_signed_out_sees_hero_and_steps(self, client, home_url):
        response = client.get(home_url)

        assert response.status_code == 200
        assert "home.html" in [t.name for t in response.templates]
        html = response.content.decode()
        assert "Find a sub who fits your league." in html
        assert "I need a sub" in html
        assert "I want to sub" in html
        assert 'id="how-it-works"' in html

    def test_mode_panes_share_space_so_toggling_keeps_layout(self, client, home_url):
        html = client.get(home_url).content.decode()

        # Both panes sit in the same grid cell and the inactive one is
        # `invisible` (keeps its space), never removed with `hidden`.
        assert html.count("col-start-1 row-start-1") == 2
        assert 'class="invisible col-start-1 row-start-1' in html
        assert "x-bind:hidden" not in html
        # A growing text wrapper in each pane pins both buttons to the bottom.
        assert html.count('<div class="flex flex-1 flex-col gap-4">') == 2

    def test_signed_in_without_profile_goes_to_onboarding(self, client, home_url):
        user = User.objects.create_user(
            "jordan@example.com", "c0rrect-Horse-battery", display_name="Jordan"
        )
        client.force_login(user)

        response = client.get(home_url)

        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:onboarding")

    def test_onboarded_user_sees_empty_dashboard(self, client, home_url):
        user = User.objects.create_user(
            "jordan@example.com",
            "c0rrect-Horse-battery",
            display_name="Jordan",
            gender=Gender.WOMAN,
            skill_tier=SkillTier.NOVICE,
            main_positions=[Position.ALL_AROUND],
        )
        client.force_login(user)

        html = client.get(home_url).content.decode()

        assert "Your games" in html
        assert "No games yet" in html
        assert "Find a sub who fits your league." not in html

    def test_htmx_request_still_gets_page(self, client, home_url):
        response = client.get(home_url, headers={"HX-Request": "true"})

        assert response.status_code == 200

    def test_rejects_post(self, client, home_url):
        assert client.post(home_url).status_code == 405


class TestReadableConsoleEmailBackend:
    def test_prints_long_links_whole_on_one_line(self):
        link = (
            "http://127.0.0.1:8000/accounts/password-reset/"
            "MTM1YTVkMDktODBjNC00NGYwLWE3YTgtMzk2ZWQ5YmVlNDM4/"
            "dhy91j-3b25dca752d1575863c89bc4a0dad564/"
        )
        stream = io.StringIO()
        message = EmailMessage(
            subject="Reset your SubSet password",
            body=f"Set a new password here:\n\n{link}\n",
            from_email="webmaster@localhost",
            to=["jordan@example.com"],
        )

        ReadableConsoleEmailBackend(stream=stream).send_messages([message])

        output = stream.getvalue()
        assert link in output.splitlines()
        assert "=\n" not in output
        assert "Subject: Reset your SubSet password" in output
        assert "To: jordan@example.com" in output
