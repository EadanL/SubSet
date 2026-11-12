import datetime

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from accounts.models import User
from core.choices import (
    Division,
    SkillTier,
    Surface,
    TeamSize,
    VerificationStatus,
    Weekday,
)
from leagues.models import League, Organizer, OrganizerRegistration
from leagues.services import (
    can_edit_league,
    can_sub_in,
    create_league,
    create_organizer,
    declare_registration,
    update_league,
    withdraw_registration,
)

pytestmark = pytest.mark.django_db

PASSWORD = "c0rrect-Horse-battery"


def assert_integrity_error(func):
    with pytest.raises(IntegrityError), transaction.atomic():
        func()


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


def unsaved_league(**overrides):
    return League(**league_fields(**overrides))


@pytest.fixture
def player():
    return User.objects.create_user("jordan@example.com", PASSWORD, display_name="J")


@pytest.fixture
def other_player():
    return User.objects.create_user("casey@example.com", PASSWORD, display_name="C")


@pytest.fixture
def guest():
    return User.objects.create_guest("Sam", phone="555-0100")


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
            name="Thursday 4s",
            organizer=organizer,
            subs_must_be_registered=True,
            team_size=TeamSize.FOURS,
            division=Division.WOMENS,
        ),
    )


class TestOrganizer:
    def test_create_collapses_whitespace(self, player):
        organizer = create_organizer(created_by=player, name="  Northside   Rec ")

        assert organizer.name == "Northside Rec"
        assert organizer.created_by == player

    @pytest.mark.parametrize("name", ["Northside Rec", "NORTHSIDE rec"])
    def test_duplicate_name_ignoring_case(self, organizer, player, name):
        with pytest.raises(ValidationError) as exc_info:
            create_organizer(created_by=player, name=name)

        assert "An organizer with this name already exists." in str(exc_info.value)

    def test_blank_name_rejected(self, player):
        with pytest.raises(ValidationError) as exc_info:
            create_organizer(created_by=player, name="   ")

        assert "name" in exc_info.value.message_dict

    def test_database_blocks_duplicates_and_blanks(self, organizer):
        assert_integrity_error(
            lambda: Organizer.objects.bulk_create([Organizer(name="northside rec")])
        )
        assert_integrity_error(lambda: Organizer.objects.bulk_create([Organizer()]))


class TestLeagueDefaults:
    def test_new_league_is_unverified_in_calgary_time(self, league, player):
        assert league.verification_status == VerificationStatus.UNVERIFIED
        assert league.timezone == "America/Edmonton"
        assert league.surface == Surface.INDOOR
        assert league.created_by == player

    def test_text_fields_collapse_whitespace(self, player):
        league = create_league(
            created_by=player,
            **league_fields(name="  Tuesday   Coed  B ", city=" Calgary "),
        )

        assert league.name == "Tuesday Coed B"
        assert league.city == "Calgary"


class TestWomenMinimum:
    @pytest.mark.parametrize(
        "division, team_size, minimum",
        [
            (Division.COED, TeamSize.SIXES, 1),
            (Division.COED, TeamSize.SIXES, 6),
            (Division.REVERSE_COED, TeamSize.FOURS, 2),
            (Division.COED, TeamSize.DOUBLES, 1),
            (Division.MENS, TeamSize.SIXES, None),
            (Division.WOMENS, TeamSize.SIXES, None),
            (Division.OPEN, TeamSize.FOURS, None),
        ],
    )
    def test_valid_combinations(self, division, team_size, minimum):
        league = unsaved_league(
            division=division, team_size=team_size, min_women_on_court=minimum
        )

        league.full_clean()
        league.save()

    @pytest.mark.parametrize(
        "division, team_size, minimum, message",
        [
            (Division.COED, TeamSize.SIXES, None, "Co-ed leagues need a minimum"),
            (
                Division.REVERSE_COED,
                TeamSize.FOURS,
                None,
                "Reverse co-ed leagues need a minimum",
            ),
            (Division.COED, TeamSize.SIXES, 0, "at least 1"),
            (Division.COED, TeamSize.FOURS, 5, "more than the team size (4s)"),
            (Division.MENS, TeamSize.SIXES, 2, "Only co-ed and reverse co-ed"),
            (Division.WOMENS, TeamSize.SIXES, 6, "Only co-ed and reverse co-ed"),
        ],
    )
    def test_invalid_combinations_report_one_field_error(
        self, division, team_size, minimum, message
    ):
        league = unsaved_league(
            division=division, team_size=team_size, min_women_on_court=minimum
        )

        with pytest.raises(ValidationError) as exc_info:
            league.full_clean()

        # Field error only; the backstop constraint adds no duplicate message.
        errors = exc_info.value.message_dict
        assert set(errors) == {"min_women_on_court"}
        assert message in errors["min_women_on_court"][0]

    @pytest.mark.parametrize(
        "division, team_size, minimum",
        [
            (Division.COED, TeamSize.SIXES, None),
            (Division.REVERSE_COED, TeamSize.FOURS, None),
            (Division.COED, TeamSize.SIXES, 0),
            (Division.COED, TeamSize.FOURS, 5),
            (Division.MENS, TeamSize.SIXES, 2),
        ],
    )
    def test_database_backstop(self, division, team_size, minimum):
        # bulk_create skips clean(), so only the CheckConstraint applies.
        assert_integrity_error(
            lambda: League.objects.bulk_create(
                [
                    unsaved_league(
                        division=division,
                        team_size=team_size,
                        min_women_on_court=minimum,
                    )
                ]
            )
        )


class TestLeagueRules:
    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"game_duration_min": 5}, "game_duration_min"),
            ({"game_duration_min": 241}, "game_duration_min"),
            ({"matches_per_night": 0}, "matches_per_night"),
            ({"matches_per_night": 11}, "matches_per_night"),
            ({"timezone": "Mars/Olympus_Mons"}, "timezone"),
            ({"weekday": 7}, "weekday"),
            ({"tier": 6}, "tier"),
            ({"team_size": 5}, "team_size"),
            ({"name": "  "}, "name"),
        ],
    )
    def test_field_errors(self, overrides, field):
        with pytest.raises(ValidationError) as exc_info:
            unsaved_league(**overrides).full_clean()

        assert field in exc_info.value.message_dict

    def test_registered_subs_need_an_organizer(self):
        league = unsaved_league(subs_must_be_registered=True)

        with pytest.raises(ValidationError) as exc_info:
            league.full_clean()

        assert set(exc_info.value.message_dict) == {"subs_must_be_registered"}

    @pytest.mark.parametrize(
        "overrides",
        [
            {"subs_must_be_registered": True},
            {"game_duration_min": 5},
            {"matches_per_night": 0},
            {"weekday": 9},
            {"division": "corporate", "min_women_on_court": None},
            {"city": ""},
        ],
    )
    def test_database_backstops(self, overrides):
        assert_integrity_error(
            lambda: League.objects.bulk_create([unsaved_league(**overrides)])
        )

    def test_exact_duplicate_is_rejected_ignoring_case(self, league, player):
        with pytest.raises(ValidationError) as exc_info:
            create_league(
                created_by=player,
                **league_fields(
                    name="TUESDAY coed b", venue_name="riverside rec centre"
                ),
            )

        assert "already plays at this venue on the same night and time" in str(
            exc_info.value
        )

    def test_different_night_or_time_is_not_a_duplicate(self, league, player):
        create_league(created_by=player, **league_fields(weekday=Weekday.WEDNESDAY))
        create_league(
            created_by=player, **league_fields(start_time=datetime.time(21, 0))
        )

        assert League.objects.count() == 3

    def test_removed_league_does_not_block_resubmission(self, league, player):
        League.objects.filter(pk=league.pk).update(
            verification_status=VerificationStatus.REMOVED
        )

        create_league(created_by=player, **league_fields())

        assert League.objects.count() == 2

    def test_visible_excludes_removed(self, league, player):
        removed = create_league(created_by=player, **league_fields(name="Fake League"))
        League.objects.filter(pk=removed.pk).update(
            verification_status=VerificationStatus.REMOVED
        )

        assert list(League.objects.visible()) == [league]


class TestCreateLeague:
    def test_clears_women_minimum_for_other_divisions(self, player):
        league = create_league(
            created_by=player,
            **league_fields(division=Division.MENS, min_women_on_court=2),
        )

        assert league.min_women_on_court is None

    @pytest.mark.parametrize("field", ["verification_status", "created_by", "id"])
    def test_rejects_fields_submitters_cannot_set(self, player, field):
        with pytest.raises(TypeError):
            create_league(created_by=player, **league_fields(**{field: None}))

        assert not League.objects.exists()


class TestUpdateLeague:
    def test_submitter_can_edit_while_unverified(self, league, player):
        update_league(league, editor=player, name="Tuesday Coed A", tier=4)

        league.refresh_from_db()
        assert league.name == "Tuesday Coed A"
        assert league.tier == SkillTier.ADVANCED

    def test_other_players_cannot_edit(self, league, other_player):
        assert not can_edit_league(other_player, league)
        with pytest.raises(PermissionDenied):
            update_league(league, editor=other_player, name="Hijacked")

    def test_anonymous_cannot_edit(self, league):
        assert not can_edit_league(AnonymousUser(), league)

    @pytest.mark.parametrize(
        "status", [VerificationStatus.VERIFIED, VerificationStatus.REMOVED]
    )
    def test_submitter_cannot_edit_once_reviewed(self, league, player, status):
        league.verification_status = status
        league.save()

        with pytest.raises(PermissionDenied):
            update_league(league, editor=player, name="Too late")

    def test_switching_to_mens_clears_minimum(self, league, player):
        update_league(league, editor=player, division=Division.MENS)

        league.refresh_from_db()
        assert league.min_women_on_court is None

    def test_switching_to_coed_requires_minimum(self, player):
        league = create_league(
            created_by=player, **league_fields(division=Division.MENS)
        )

        with pytest.raises(ValidationError) as exc_info:
            update_league(league, editor=player, division=Division.COED)

        assert set(exc_info.value.message_dict) == {"min_women_on_court"}
        # In-memory league is reset as well as the database row.
        assert league.division == Division.MENS

    def test_rejects_fields_submitters_cannot_set(self, league, player):
        with pytest.raises(TypeError):
            update_league(
                league,
                editor=player,
                verification_status=VerificationStatus.VERIFIED,
            )


class TestRegistrations:
    def test_declare_is_safe_to_repeat(self, player, organizer):
        first = declare_registration(user=player, organizer=organizer)
        second = declare_registration(user=player, organizer=organizer)

        assert first == second
        assert OrganizerRegistration.objects.count() == 1

    def test_guests_cannot_register(self, guest, organizer):
        with pytest.raises(ValidationError):
            declare_registration(user=guest, organizer=organizer)

        registration = OrganizerRegistration(user=guest, organizer=organizer)
        with pytest.raises(ValidationError) as exc_info:
            registration.full_clean()
        assert "user" in exc_info.value.message_dict

    def test_withdraw_reports_whether_one_existed(self, player, organizer):
        declare_registration(user=player, organizer=organizer)

        assert withdraw_registration(user=player, organizer=organizer) is True
        assert withdraw_registration(user=player, organizer=organizer) is False

    def test_database_allows_one_per_organizer(self, player, organizer):
        declare_registration(user=player, organizer=organizer)

        assert_integrity_error(
            lambda: OrganizerRegistration.objects.bulk_create(
                [OrganizerRegistration(user=player, organizer=organizer)]
            )
        )

    def test_organizer_with_leagues_cannot_be_deleted(self, restricted_league):
        with pytest.raises(ProtectedError), transaction.atomic():
            restricted_league.organizer.delete()


class TestCanSubIn:
    def test_unrestricted_league_is_open_to_everyone(self, league, player, guest):
        assert can_sub_in(AnonymousUser(), league)
        assert can_sub_in(guest, league)
        assert can_sub_in(player, league)

    def test_restricted_league_needs_registration(
        self, restricted_league, player, guest
    ):
        assert not can_sub_in(AnonymousUser(), restricted_league)
        assert not can_sub_in(guest, restricted_league)
        assert not can_sub_in(player, restricted_league)

        declare_registration(user=player, organizer=restricted_league.organizer)

        assert can_sub_in(player, restricted_league)

    def test_registration_with_another_organizer_does_not_count(
        self, restricted_league, player
    ):
        other = create_organizer(created_by=player, name="Southside Sports")
        declare_registration(user=player, organizer=other)

        assert not can_sub_in(player, restricted_league)

    def test_removed_league_accepts_no_one(self, league, player):
        league.verification_status = VerificationStatus.REMOVED

        assert not can_sub_in(player, league)


class TestAdmin:
    @pytest.fixture
    def admin_client(self, client):
        admin = User.objects.create_superuser(
            "admin@example.com", PASSWORD, display_name="Admin"
        )
        client.force_login(admin)
        return client

    @pytest.mark.parametrize(
        "name",
        [
            "admin:leagues_league_changelist",
            "admin:leagues_league_add",
            "admin:leagues_organizer_changelist",
            "admin:leagues_organizerregistration_changelist",
        ],
    )
    def test_pages_load(self, admin_client, league, name):
        assert admin_client.get(reverse(name)).status_code == 200

    @pytest.mark.parametrize(
        "action, status",
        [
            ("mark_verified", VerificationStatus.VERIFIED),
            ("mark_removed", VerificationStatus.REMOVED),
        ],
    )
    def test_bulk_actions(self, admin_client, league, action, status):
        admin_client.post(
            reverse("admin:leagues_league_changelist"),
            {"action": action, "_selected_action": [str(league.pk)]},
        )

        league.refresh_from_db()
        assert league.verification_status == status
