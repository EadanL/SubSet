import uuid

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts.models import AccountType, User
from accounts.services import complete_onboarding, register_full_account
from core.choices import Gender, Position, SkillTier

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

    def test_full_clean_requires_email_for_full_account(self):
        user = User(display_name="No Email", account_type=AccountType.FULL)
        user.set_unusable_password()

        with pytest.raises(ValidationError) as exc_info:
            user.full_clean()

        # Field error from clean(), not the generic constraint message.
        assert exc_info.value.message_dict == {
            "email": ["Full accounts require an email address."]
        }

    def test_full_clean_normalizes_email_before_validating(self):
        user = User(email="  Padded@Example.COM ", display_name="Padded")
        user.set_unusable_password()

        user.full_clean()

        assert user.email == "padded@example.com"

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


def profile_user(skill_tier=None, tier_flex_down=0, tier_flex_up=0):
    user = User(
        email="range@example.com",
        display_name="Range",
        skill_tier=skill_tier,
        tier_flex_down=tier_flex_down,
        tier_flex_up=tier_flex_up,
    )
    user.set_unusable_password()
    return user


class TestTierFlexRule:
    @pytest.mark.parametrize(
        "tier, down, up",
        [
            (None, 0, 0),
            (SkillTier.BEGINNER, 0, 0),
            (SkillTier.BEGINNER, 0, 4),
            (SkillTier.ELITE, 4, 0),
            (SkillTier.INTERMEDIATE, 2, 2),
        ],
    )
    def test_ranges_on_the_scale_are_valid(self, tier, down, up):
        user = profile_user(tier, down, up)

        user.full_clean()
        user.save()

    @pytest.mark.parametrize(
        "tier, down, up, error_fields",
        [
            (SkillTier.BEGINNER, 1, 0, {"tier_flex_down"}),
            (SkillTier.ELITE, 0, 1, {"tier_flex_up"}),
            (SkillTier.INTERMEDIATE, 3, 3, {"tier_flex_down", "tier_flex_up"}),
            (None, 1, 0, {"skill_tier"}),
            (None, 0, 1, {"skill_tier"}),
        ],
    )
    def test_clean_reports_field_errors_once(self, tier, down, up, error_fields):
        user = profile_user(tier, down, up)

        with pytest.raises(ValidationError) as exc_info:
            user.full_clean()

        # Field-keyed errors only: the backstop constraint must not add a
        # duplicate non-field error.
        assert set(exc_info.value.message_dict) == error_fields

    def test_error_message_names_the_tier(self):
        user = profile_user(SkillTier.NOVICE, 2, 0)

        with pytest.raises(ValidationError) as exc_info:
            user.full_clean()

        assert exc_info.value.message_dict["tier_flex_down"] == [
            "From Novice (C) you can go at most 1 tier(s) down."
        ]

    @pytest.mark.parametrize(
        "tier, down, up",
        [
            (SkillTier.BEGINNER, 1, 0),
            (SkillTier.ELITE, 0, 1),
            (None, 1, 0),
            (None, 0, 1),
            (0, 0, 0),
            (6, 0, 0),
        ],
    )
    def test_database_rejects_out_of_scale_ranges(self, tier, down, up):
        # bulk_create skips clean(), so only the CheckConstraint applies.
        assert_integrity_error(
            lambda: User.objects.bulk_create([profile_user(tier, down, up)])
        )


class TestPositionRules:
    @pytest.mark.parametrize(
        "main, sub",
        [
            ([], []),
            ([Position.SETTER], []),
            ([Position.SETTER, Position.LIBERO], [Position.OPPOSITE]),
            ([Position.ALL_AROUND], [Position.SETTER, Position.MIDDLE_BLOCKER]),
        ],
    )
    def test_valid_combinations(self, full_user, main, sub):
        full_user.main_positions, full_user.sub_positions = main, sub

        full_user.full_clean()
        full_user.save()

    @pytest.mark.parametrize(
        "main, sub, error_fields",
        [
            (
                [Position.SETTER, Position.LIBERO, Position.OPPOSITE],
                [],
                {"main_positions"},
            ),
            ([Position.SETTER, Position.SETTER], [], {"main_positions"}),
            ([], [Position.LIBERO, Position.LIBERO], {"sub_positions"}),
            ([Position.SETTER], [Position.SETTER], {"sub_positions"}),
            (["goalkeeper"], [], {"main_positions"}),
            ([], ["goalkeeper"], {"sub_positions"}),
        ],
    )
    def test_clean_reports_field_errors_once(self, full_user, main, sub, error_fields):
        full_user.main_positions, full_user.sub_positions = main, sub

        with pytest.raises(ValidationError) as exc_info:
            full_user.full_clean()

        # Field-keyed errors only, no duplicate constraint message.
        assert set(exc_info.value.message_dict) == error_fields

    def test_overlap_message_names_the_positions(self, full_user):
        full_user.main_positions = [Position.SETTER, Position.LIBERO]
        full_user.sub_positions = [Position.LIBERO, Position.SETTER]

        with pytest.raises(ValidationError) as exc_info:
            full_user.full_clean()

        assert exc_info.value.message_dict["sub_positions"] == [
            "Already one of your main positions: Libero, Setter."
        ]

    @pytest.mark.parametrize(
        "main, sub",
        [
            ([Position.SETTER, Position.LIBERO, Position.OPPOSITE], []),
            ([Position.SETTER], [Position.SETTER]),
            (["goalkeeper"], []),
            ([], ["goalkeeper"]),
        ],
    )
    def test_database_rejects_invalid_positions(self, full_user, main, sub):
        # update() skips clean(), so only the CheckConstraints apply.
        assert_integrity_error(
            lambda: User.objects.filter(pk=full_user.pk).update(
                main_positions=main, sub_positions=sub
            )
        )


class TestIsOnboarded:
    def test_new_full_account_is_not_onboarded(self, full_user):
        assert not full_user.is_onboarded

    @pytest.mark.parametrize(
        "tier, gender, main",
        [
            (SkillTier.NOVICE, "", [Position.SETTER]),
            (None, Gender.WOMAN, [Position.SETTER]),
            (SkillTier.NOVICE, Gender.WOMAN, []),
        ],
    )
    def test_requires_tier_gender_and_main_position(
        self, full_user, tier, gender, main
    ):
        full_user.skill_tier = tier
        full_user.gender = gender
        full_user.main_positions = main

        assert not full_user.is_onboarded

    def test_tier_gender_and_main_position_complete_onboarding(self, full_user):
        full_user.skill_tier = SkillTier.NOVICE
        full_user.gender = Gender.PREFER_NOT_TO_SAY
        full_user.main_positions = [Position.ALL_AROUND]

        assert full_user.is_onboarded

    def test_guest_is_never_onboarded(self):
        guest = User.objects.create_guest("Sam", phone="555-0100")
        guest.skill_tier = SkillTier.NOVICE
        guest.gender = Gender.WOMAN
        guest.main_positions = [Position.SETTER]

        assert not guest.is_onboarded


class TestRegisterFullAccount:
    def test_creates_normalized_full_account(self):
        user = register_full_account(
            email=" New@Example.COM ", password=PASSWORD, display_name="  New  "
        )

        user.refresh_from_db()
        assert user.email == "new@example.com"
        assert user.display_name == "New"
        assert user.account_type == AccountType.FULL
        assert user.check_password(PASSWORD)
        assert not user.is_onboarded

    @pytest.mark.parametrize("email", ["JORDAN@example.com", "jordan@example.com"])
    def test_rejects_registered_email(self, full_user, email):
        with pytest.raises(ValidationError) as exc_info:
            register_full_account(email=email, password=PASSWORD, display_name="Dup")

        assert set(exc_info.value.message_dict) == {"email"}

    def test_rejects_email_held_by_guest(self):
        User.objects.create_guest("Sam", email="sam@example.com")

        with pytest.raises(ValidationError) as exc_info:
            register_full_account(
                email="Sam@Example.com", password=PASSWORD, display_name="Sam"
            )

        assert set(exc_info.value.message_dict) == {"email"}
        assert User.objects.get(email="sam@example.com").is_guest

    @pytest.mark.parametrize(
        "email, display_name, error_field",
        [
            ("not-an-email", "Valid", "email"),
            ("", "Valid", "email"),
            ("valid@example.com", "   ", "display_name"),
        ],
    )
    def test_rejects_invalid_fields(self, email, display_name, error_field):
        with pytest.raises(ValidationError) as exc_info:
            register_full_account(
                email=email, password=PASSWORD, display_name=display_name
            )

        assert error_field in exc_info.value.message_dict
        assert not User.objects.exists()

    @pytest.mark.parametrize("password", ["short", "password123", "12345678901"])
    def test_rejects_weak_password(self, password):
        with pytest.raises(ValidationError) as exc_info:
            register_full_account(
                email="weak@example.com", password=password, display_name="Weak"
            )

        assert set(exc_info.value.message_dict) == {"password"}
        assert not User.objects.exists()


class TestCompleteOnboarding:
    REQUIRED = {
        "gender": Gender.MAN,
        "skill_tier": SkillTier.NOVICE,
        "main_positions": [Position.SETTER],
    }

    def test_saves_profile_and_onboards(self, full_user):
        complete_onboarding(
            full_user,
            gender=Gender.WOMAN,
            skill_tier=SkillTier.INTERMEDIATE,
            main_positions=[Position.SETTER],
            sub_positions=[Position.LIBERO],
            tier_flex_down=1,
            tier_flex_up=1,
            travel_radius_km=25,
            phone=" 555-0100 ",
            display_name=" Jordan K ",
        )

        full_user.refresh_from_db()
        assert full_user.is_onboarded
        assert full_user.gender == Gender.WOMAN
        assert full_user.skill_tier == SkillTier.INTERMEDIATE
        assert full_user.main_positions == [Position.SETTER]
        assert full_user.sub_positions == [Position.LIBERO]
        assert (full_user.tier_flex_down, full_user.tier_flex_up) == (1, 1)
        assert full_user.travel_radius_km == 25
        assert full_user.phone == "555-0100"
        assert full_user.display_name == "Jordan K"

    def test_positions_are_deduplicated_and_ordered(self, full_user):
        complete_onboarding(
            full_user,
            gender=Gender.MAN,
            skill_tier=SkillTier.NOVICE,
            main_positions=[Position.LIBERO, Position.SETTER, Position.LIBERO],
            sub_positions=[Position.ALL_AROUND, Position.OPPOSITE],
        )

        full_user.refresh_from_db()
        assert full_user.main_positions == [Position.SETTER, Position.LIBERO]
        assert full_user.sub_positions == [Position.OPPOSITE, Position.ALL_AROUND]

    def test_sub_positions_are_optional(self, full_user):
        complete_onboarding(full_user, **self.REQUIRED)

        full_user.refresh_from_db()
        assert full_user.sub_positions == []
        assert full_user.is_onboarded

    def test_keeps_display_name_when_omitted(self, full_user):
        complete_onboarding(full_user, **self.REQUIRED)

        full_user.refresh_from_db()
        assert full_user.display_name == "Jordan"

    def test_updates_timestamp(self, full_user):
        before = full_user.updated_at

        complete_onboarding(full_user, **self.REQUIRED)

        full_user.refresh_from_db()
        assert full_user.updated_at > before

    @pytest.mark.parametrize(
        "overrides, error_fields",
        [
            ({"gender": ""}, {"gender"}),
            ({"skill_tier": None}, {"skill_tier"}),
            ({"main_positions": []}, {"main_positions"}),
            (
                {"gender": "", "skill_tier": None, "main_positions": []},
                {"gender", "skill_tier", "main_positions"},
            ),
        ],
    )
    def test_requires_gender_tier_and_main_position(
        self, full_user, overrides, error_fields
    ):
        with pytest.raises(ValidationError) as exc_info:
            complete_onboarding(full_user, **{**self.REQUIRED, **overrides})

        assert set(exc_info.value.message_dict) == error_fields

    def test_invalid_range_leaves_user_unchanged(self, full_user):
        with pytest.raises(ValidationError) as exc_info:
            complete_onboarding(
                full_user,
                **{**self.REQUIRED, "skill_tier": SkillTier.BEGINNER},
                tier_flex_down=1,
            )

        assert set(exc_info.value.message_dict) == {"tier_flex_down"}
        # In-memory instance is reset as well as the database row.
        assert full_user.skill_tier is None
        assert full_user.gender == ""
        assert full_user.main_positions == []
        full_user.refresh_from_db()
        assert not full_user.is_onboarded

    def test_position_in_both_lists_is_rejected(self, full_user):
        with pytest.raises(ValidationError) as exc_info:
            complete_onboarding(
                full_user, **self.REQUIRED, sub_positions=[Position.SETTER]
            )

        assert set(exc_info.value.message_dict) == {"sub_positions"}
        assert full_user.main_positions == []

    def test_rejects_invalid_choice(self, full_user):
        with pytest.raises(ValidationError) as exc_info:
            complete_onboarding(full_user, **{**self.REQUIRED, "gender": "robot"})

        assert "gender" in exc_info.value.message_dict

    def test_rejects_guest(self):
        guest = User.objects.create_guest("Sam", phone="555-0100")

        with pytest.raises(ValidationError):
            complete_onboarding(guest, **self.REQUIRED)

        guest.refresh_from_db()
        assert guest.skill_tier is None
