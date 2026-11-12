import re

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import AccountType, User

pytestmark = pytest.mark.django_db

PASSWORD = "c0rrect-Horse-battery"
HTMX = {"HX-Request": "true"}


@pytest.fixture
def full_user():
    return User.objects.create_user(
        "jordan@example.com", PASSWORD, display_name="Jordan"
    )


def signup_data(**overrides):
    return {
        "email": "New.Player@Example.com",
        "display_name": "New Player",
        "password1": PASSWORD,
        "password2": PASSWORD,
        **overrides,
    }


def assert_fragment(response):
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html
    return html


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class TestSignup:
    url = reverse("accounts:signup")

    def test_get_renders_full_page(self, client):
        response = client.get(self.url)

        html = response.content.decode()
        assert response.status_code == 200
        assert "<html" in html
        assert "Create your account" in html
        assert 'hx-post="/accounts/signup/"' in html

    def test_signed_in_user_is_redirected_home(self, client, full_user):
        client.force_login(full_user)

        response = client.get(self.url)

        assert response.status_code == 302
        assert response["Location"] == reverse("home")

    def test_htmx_valid_submit_creates_account_and_goes_to_onboarding(self, client):
        response = client.post(self.url, signup_data(), headers=HTMX)

        assert response.status_code == 200
        assert response["HX-Redirect"] == reverse("accounts:onboarding")
        user = User.objects.get(email="new.player@example.com")
        assert user.account_type == AccountType.FULL
        assert user.display_name == "New Player"
        assert client.session["_auth_user_id"] == str(user.pk)
        assert "Account created" in message_texts(response)

    def test_plain_valid_submit_redirects_to_onboarding(self, client):
        response = client.post(self.url, signup_data())

        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:onboarding")

    @pytest.mark.parametrize("email", ["jordan@example.com", "JORDAN@Example.com"])
    def test_registered_email_shows_error(self, client, full_user, email):
        response = client.post(self.url, signup_data(email=email), headers=HTMX)

        html = assert_fragment(response)
        assert "An account with this email already exists." in html
        assert User.objects.count() == 1

    def test_email_held_by_guest_shows_standard_error(self, client):
        User.objects.create_guest("Sam", email="sam@example.com")

        response = client.post(
            self.url, signup_data(email="Sam@Example.com"), headers=HTMX
        )

        html = assert_fragment(response)
        assert "An account with this email already exists." in html
        assert User.objects.get(email="sam@example.com").is_guest

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"email": ""}, "This field is required."),
            ({"email": "not-an-email"}, "Enter a valid email address."),
            ({"display_name": "J"}, "at least 2 characters"),
            ({"password2": "different-Horse-9"}, "didn’t match"),
            ({"password1": "password123", "password2": "password123"}, "too common"),
            (
                {
                    "display_name": "Volleyballer",
                    "password1": "volleyballer",
                    "password2": "volleyballer",
                },
                "too similar",
            ),
        ],
    )
    def test_invalid_input_rerenders_fragment_with_error(
        self, client, overrides, expected
    ):
        response = client.post(self.url, signup_data(**overrides), headers=HTMX)

        html = assert_fragment(response)
        assert expected in html
        assert 'aria-invalid="true"' in html
        assert not User.objects.exists()

    def test_service_errors_are_shown_on_the_form(self, client, monkeypatch):
        def fail(**kwargs):
            raise ValidationError(
                {"email": ["Taken just now."], "password": ["Too weak."]}
            )

        monkeypatch.setattr("accounts.forms.register_full_account", fail)

        response = client.post(self.url, signup_data(), headers=HTMX)

        html = assert_fragment(response)
        assert "Taken just now." in html
        assert "Too weak." in html
        assert "_auth_user_id" not in client.session


class TestLogin:
    url = reverse("accounts:login")

    def test_get_renders_full_page_with_email_label(self, client):
        response = client.get(self.url)

        html = response.content.decode()
        assert response.status_code == 200
        assert "<html" in html
        assert ">Email</label>" in html
        assert 'type="email"' in html

    def test_signed_in_user_is_redirected(self, client, full_user):
        client.force_login(full_user)

        response = client.get(self.url)

        assert response.status_code == 302

    def test_htmx_valid_login_with_mixed_case_email(self, client, full_user):
        response = client.post(
            self.url,
            {"username": "Jordan@Example.COM", "password": PASSWORD},
            headers=HTMX,
        )

        assert response["HX-Redirect"] == reverse("home")
        assert client.session["_auth_user_id"] == str(full_user.pk)

    def test_plain_valid_login_redirects(self, client, full_user):
        response = client.post(
            self.url, {"username": "jordan@example.com", "password": PASSWORD}
        )

        assert response.status_code == 302
        assert response["Location"] == reverse("home")

    def test_safe_next_is_followed(self, client, full_user):
        response = client.post(
            self.url,
            {
                "username": "jordan@example.com",
                "password": PASSWORD,
                "next": "/?from=login",
            },
            headers=HTMX,
        )

        assert response["HX-Redirect"] == "/?from=login"

    def test_unsafe_next_is_ignored(self, client, full_user):
        response = client.post(
            self.url,
            {
                "username": "jordan@example.com",
                "password": PASSWORD,
                "next": "https://evil.example.com/",
            },
            headers=HTMX,
        )

        assert response["HX-Redirect"] == reverse("home")

    def test_next_survives_a_failed_attempt(self, client, full_user):
        response = client.post(
            self.url,
            {"username": "jordan@example.com", "password": "wrong", "next": "/?x=1"},
            headers=HTMX,
        )

        html = assert_fragment(response)
        assert 'name="next" value="/?x=1"' in html

    @pytest.mark.parametrize(
        "case", ["wrong_password", "unknown_email", "guest", "inactive"]
    )
    def test_every_failure_shows_the_same_generic_error(self, client, case):
        User.objects.create_user("jordan@example.com", PASSWORD, display_name="J")
        User.objects.create_guest("Sam", email="sam@example.com")
        User.objects.create_user(
            "off@example.com", PASSWORD, display_name="Off", is_active=False
        )
        username, password = {
            "wrong_password": ("jordan@example.com", "nope"),
            "unknown_email": ("nobody@example.com", PASSWORD),
            # Guests have an unusable password, so any password fails.
            "guest": ("sam@example.com", "any-Password-1"),
            "inactive": ("off@example.com", PASSWORD),
        }[case]

        response = client.post(
            self.url, {"username": username, "password": password}, headers=HTMX
        )

        html = assert_fragment(response)
        assert "That email and password don" in html
        assert "_auth_user_id" not in client.session


class TestLogout:
    url = reverse("accounts:logout")

    def test_get_is_not_allowed(self, client, full_user):
        client.force_login(full_user)

        assert client.get(self.url).status_code == 405

    def test_post_logs_out_and_redirects_home(self, client, full_user):
        client.force_login(full_user)

        response = client.post(self.url, follow=True)

        assert response.redirect_chain[-1][0] == reverse("home")
        assert "_auth_user_id" not in client.session
        assert "Logged out" in response.content.decode()


class TestNav:
    def test_signed_out_nav_and_hero_link_to_signup(self, client):
        html = client.get(reverse("home")).content.decode()

        assert f'href="{reverse("accounts:login")}"' in html
        assert html.count(f'href="{reverse("accounts:signup")}"') >= 3
        assert 'href="#how-it-works"' not in html

    def test_signed_in_nav_shows_logout_form(self, client, full_user):
        client.force_login(full_user)

        html = client.get(reverse("home"), follow=True).content.decode()

        assert f'action="{reverse("accounts:logout")}"' in html
        assert f'href="{reverse("accounts:profile")}"' in html
        assert f'href="{reverse("accounts:login")}"' not in html


class TestPasswordReset:
    url = reverse("accounts:password_reset")
    done_url = reverse("accounts:password_reset_done")

    @staticmethod
    def reset_link(email):
        match = re.search(
            r"https?://[^/\s]+(/accounts/password-reset/\S+/)", email.body
        )
        assert match, email.body
        return match.group(1)

    def test_login_page_links_to_reset(self, client):
        html = client.get(reverse("accounts:login")).content.decode()

        assert f'href="{self.url}"' in html
        assert "Forgot your password?" in html

    def test_get_renders_form(self, client):
        response = client.get(self.url)

        html = response.content.decode()
        assert response.status_code == 200
        assert "Send reset link" in html
        assert ">Email</label>" in html

    def test_sends_one_email_for_full_account_with_mixed_case(
        self, client, full_user, mailoutbox
    ):
        response = client.post(self.url, {"email": "JORDAN@Example.com"})

        assert response.status_code == 302
        assert response["Location"] == self.done_url
        assert len(mailoutbox) == 1
        email = mailoutbox[0]
        assert email.to == ["jordan@example.com"]
        assert email.subject == "Reset your SubSet password"
        assert "Hi Jordan," in email.body
        assert "&#x27;" not in email.body and "&amp;" not in email.body
        self.reset_link(email)

    @pytest.mark.parametrize("case", ["unknown", "guest", "inactive"])
    def test_no_email_but_same_redirect_for_other_addresses(
        self, client, mailoutbox, case
    ):
        User.objects.create_guest("Sam", email="sam@example.com")
        User.objects.create_user(
            "off@example.com", PASSWORD, display_name="Off", is_active=False
        )
        email = {
            "unknown": "nobody@example.com",
            "guest": "sam@example.com",
            "inactive": "off@example.com",
        }[case]

        response = client.post(self.url, {"email": email})

        assert response["Location"] == self.done_url
        assert mailoutbox == []

    def test_full_flow_sets_new_password_and_link_works_once(
        self, client, full_user, mailoutbox
    ):
        client.post(self.url, {"email": "jordan@example.com"})
        link = self.reset_link(mailoutbox[0])

        # Django swaps the token for a session marker and redirects.
        set_password_url = client.get(link)["Location"]
        form_page = client.get(set_password_url).content.decode()
        assert "Set a new password" in form_page

        mismatch = client.post(
            set_password_url,
            {"new_password1": "Fresh-Serve-42", "new_password2": "Other-Serve-42"},
        )
        assert "didn’t match" in mismatch.content.decode()

        done = client.post(
            set_password_url,
            {"new_password1": "Fresh-Serve-42", "new_password2": "Fresh-Serve-42"},
        )
        assert done["Location"] == reverse("accounts:password_reset_complete")
        full_user.refresh_from_db()
        assert full_user.check_password("Fresh-Serve-42")
        assert not full_user.check_password(PASSWORD)

        reused = client.get(link, follow=True).content.decode()
        assert "This link no longer works" in reused
        assert "Request a new link" in reused

    def test_tampered_link_shows_invalid_page(self, client, full_user):
        url = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": "bm9wZQ", "token": "bad-token"},
        )

        html = client.get(url).content.decode()

        assert "This link no longer works" in html

    def test_complete_page_links_to_login(self, client):
        html = client.get(reverse("accounts:password_reset_complete")).content.decode()

        assert "New password set" in html
        assert f'href="{reverse("accounts:login")}"' in html


class TestPasswordEyeToggle:
    """Every password field has its own eye button inside the input, and the old
    "Show password(s)" text buttons are gone."""

    @staticmethod
    def assert_eye_toggles(html, count):
        assert html.count('aria-label="Show password"') == count
        assert html.count('x-data="{ show: false }"') == count
        assert html.count('type="password"') == count
        assert html.count("[&amp;::-ms-reveal]:hidden") == count
        assert "x-text=\"show ? 'Hide password" not in html

    def test_login_has_one_toggle(self, client):
        html = client.get(reverse("accounts:login")).content.decode()

        self.assert_eye_toggles(html, 1)

    def test_signup_has_one_toggle_per_field(self, client):
        html = client.get(reverse("accounts:signup")).content.decode()

        self.assert_eye_toggles(html, 2)

    def test_set_new_password_has_one_toggle_per_field(self, client, full_user):
        url = reverse(
            "accounts:password_reset_confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(full_user.pk)),
                "token": default_token_generator.make_token(full_user),
            },
        )

        html = client.get(url, follow=True).content.decode()

        self.assert_eye_toggles(html, 2)

    def test_toggle_survives_htmx_error_rerender(self, client):
        response = client.post(
            reverse("accounts:login"),
            {"username": "nobody@example.com", "password": "nope"},
            headers=HTMX,
        )

        self.assert_eye_toggles(assert_fragment(response), 1)
