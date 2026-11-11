import uuid

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts.models import AccountType, User

pytestmark = pytest.mark.django_db

PASSWORD = "c0rrect-Horse-battery"


def assert_integrity_error(func):
    with pytest.raises(IntegrityError), transaction.atomic():
        func()


@pytest.fixture
def full_user():
    return User.objects.create_user(
        "jordan@example.com", PASSWORD, display_name="Jordan"
    )


@pytest.fixture
def superuser():
    return User.objects.create_superuser(
        "admin@example.com", PASSWORD, display_name="Admin"
    )


class TestCreateUser:
    def test_normalizes_email_and_sets_password(self):
        user = User.objects.create_user(
            "  Jordan@Example.COM ", PASSWORD, display_name="Jordan"
        )

        assert user.email == "jordan@example.com"
        assert user.check_password(PASSWORD)
        assert user.account_type == AccountType.FULL
        assert not user.is_guest
        assert not user.is_staff
        assert not user.is_superuser

    @pytest.mark.parametrize("email", [None, "", "   "])
    def test_requires_email(self, email):
        with pytest.raises(ValueError):
            User.objects.create_user(email, PASSWORD, display_name="Nobody")

    def test_without_password_is_unusable(self):
        user = User.objects.create_user("nopass@example.com", display_name="No Pass")

        assert not user.has_usable_password()

    def test_forces_full_account_type(self):
        user = User.objects.create_user(
            "full@example.com",
            PASSWORD,
            display_name="Full",
            account_type=AccountType.GUEST,
        )

        assert user.account_type == AccountType.FULL

    def test_uuid_primary_key_and_timestamps(self, full_user):
        assert isinstance(full_user.pk, uuid.UUID)
        assert full_user.created_at is not None
        assert full_user.updated_at is not None


class TestCreateSuperuser:
    def test_sets_staff_and_superuser(self, superuser):
        assert superuser.is_staff
        assert superuser.is_superuser
        assert superuser.account_type == AccountType.FULL

    @pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
    def test_rejects_disabled_flags(self, flag):
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                "admin@example.com", PASSWORD, display_name="Admin", **{flag: False}
            )


class TestCreateGuest:
    def test_phone_only_guest(self):
        guest = User.objects.create_guest("Sam", phone=" 555-0100 ")

        assert guest.is_guest
        assert guest.email is None
        assert guest.phone == "555-0100"
        assert not guest.has_usable_password()

    def test_email_only_guest_is_normalized(self):
        guest = User.objects.create_guest("Sam", email="Sam@Example.com")

        assert guest.email == "sam@example.com"
        assert guest.phone == ""

    def test_multiple_guests_without_email(self):
        User.objects.create_guest("Sam", phone="555-0100")
        User.objects.create_guest("Alex", phone="555-0101")

        assert User.objects.filter(email__isnull=True).count() == 2

    @pytest.mark.parametrize("email, phone", [(None, ""), ("", "  "), ("  ", None)])
    def test_requires_contact(self, email, phone):
        with pytest.raises(ValueError):
            User.objects.create_guest("Ghost", email=email, phone=phone)


class TestDatabaseConstraints:
    def test_duplicate_email_rejected(self, full_user):
        assert_integrity_error(
            lambda: User.objects.create_user(
                "JORDAN@example.com", PASSWORD, display_name="Imposter"
            )
        )

    def test_case_insensitive_unique_when_save_is_bypassed(self, full_user):
        # bulk_create skips save(), so only the Lower(email) constraint applies.
        assert_integrity_error(
            lambda: User.objects.bulk_create(
                [User(email="Jordan@Example.com", display_name="Imposter")]
            )
        )

    def test_full_account_requires_email(self):
        assert_integrity_error(
            lambda: User.objects.create(
                display_name="No Email", account_type=AccountType.FULL
            )
        )

    def test_guest_requires_email_or_phone(self):
        assert_integrity_error(
            lambda: User.objects.create(
                display_name="Ghost", account_type=AccountType.GUEST
            )
        )

    def test_blank_email_rejected_when_save_is_bypassed(self):
        guest = User.objects.create_guest("Sam", phone="555-0100")

        assert_integrity_error(
            lambda: User.objects.filter(pk=guest.pk).update(email="")
        )

    def test_invalid_account_type_rejected(self):
        assert_integrity_error(
            lambda: User.objects.create(
                email="odd@example.com", display_name="Odd", account_type="vip"
            )
        )

    @pytest.mark.parametrize(
        "field", ["tier_flex_down", "tier_flex_up", "travel_radius_km"]
    )
    def test_negative_values_rejected(self, field):
        assert_integrity_error(
            lambda: User.objects.create_user(
                "neg@example.com", PASSWORD, display_name="Neg", **{field: -1}
            )
        )

    def test_full_clean_reports_case_insensitive_duplicate(self, full_user):
        user = User(email="JORDAN@EXAMPLE.COM", display_name="Imposter")
        user.set_unusable_password()

        with pytest.raises(ValidationError):
            user.full_clean()


class TestAuthentication:
    def test_auth_user_model_is_accounts_user(self):
        assert get_user_model() is User

    def test_natural_key_lookup_is_case_insensitive(self, full_user):
        assert User.objects.get_by_natural_key(" JORDAN@example.com ") == full_user

    @pytest.mark.parametrize("username", [None, "", "  "])
    def test_blank_natural_key_never_matches_guests(self, username):
        User.objects.create_guest("Sam", phone="555-0100")

        with pytest.raises(User.DoesNotExist):
            User.objects.get_by_natural_key(username)

    def test_authenticate_with_mixed_case_email(self, full_user):
        assert authenticate(username="Jordan@Example.com", password=PASSWORD) == (
            full_user
        )

    def test_guest_cannot_authenticate_with_password(self):
        User.objects.create_guest("Sam", email="sam@example.com")

        assert authenticate(username="sam@example.com", password="") is None


class TestUserAdmin:
    @pytest.fixture
    def admin_client(self, client, superuser):
        client.force_login(superuser)
        return client

    def test_changelist_and_change_pages_load(self, admin_client, full_user):
        changelist = admin_client.get(reverse("admin:accounts_user_changelist"))
        change = admin_client.get(
            reverse("admin:accounts_user_change", args=[full_user.pk])
        )

        assert changelist.status_code == 200
        assert change.status_code == 200

    def test_add_user_creates_full_account(self, admin_client):
        response = admin_client.post(
            reverse("admin:accounts_user_add"),
            {
                "email": "New.Player@Example.com",
                "display_name": "New Player",
                "usable_password": "true",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        assert response.status_code == 302
        user = User.objects.get(email="new.player@example.com")
        assert user.account_type == AccountType.FULL
        assert user.check_password(PASSWORD)
