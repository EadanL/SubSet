from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from core.choices import Gender, SkillTier
from core.models import TimeStampedModel, UUIDModel

MIN_TIER = min(SkillTier.values)
MAX_TIER = max(SkillTier.values)


def normalize_email_address(email):
    """Trim and lowercase an email address; blank values become ``None``."""
    if not email:
        return None
    return email.strip().lower() or None


class AccountType(models.TextChoices):
    FULL = "full", "Full account"
    GUEST = "guest", "Guest"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        email = normalize_email_address(username)
        if email is None:
            # Never fall through to an ``email IS NULL`` lookup, which would
            # match guest accounts.
            raise self.model.DoesNotExist
        return self.get(email=email)

    def create_user(self, email, password=None, **extra_fields):
        """Create a full account. Email is required."""
        email = normalize_email_address(email)
        if email is None:
            raise ValueError("Full accounts require an email address.")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields["account_type"] = AccountType.FULL
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)

    def create_guest(self, display_name, email=None, phone=""):
        """Create a guest account reachable by email or phone, without a password."""
        email = normalize_email_address(email)
        phone = (phone or "").strip()
        if email is None and not phone:
            raise ValueError("Guests require an email address or phone number.")
        user = self.model(
            display_name=display_name,
            email=email,
            phone=phone,
            account_type=AccountType.GUEST,
        )
        user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    # Nullable so guests can sign up with only a phone number; Postgres
    # permits multiple NULLs under a unique index.
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    display_name = models.CharField(max_length=100)
    account_type = models.CharField(
        max_length=10, choices=AccountType.choices, default=AccountType.FULL
    )
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True)
    skill_tier = models.PositiveSmallIntegerField(
        choices=SkillTier.choices, null=True, blank=True
    )
    tier_flex_down = models.PositiveSmallIntegerField(default=0)
    tier_flex_up = models.PositiveSmallIntegerField(default=0)
    travel_radius_km = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        constraints = [
            # ``unique=True`` is case-sensitive; this also covers writes that
            # bypass save(), such as ``QuerySet.update()``.
            models.UniqueConstraint(
                Lower("email"), name="accounts_user_email_ci_unique"
            ),
            models.CheckConstraint(
                condition=~Q(email=""), name="accounts_user_email_not_blank"
            ),
            models.CheckConstraint(
                condition=Q(account_type__in=AccountType.values),
                name="accounts_user_account_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(account_type=AccountType.GUEST) | Q(email__isnull=False),
                name="accounts_user_full_requires_email",
            ),
            models.CheckConstraint(
                condition=Q(account_type=AccountType.FULL)
                | Q(email__isnull=False)
                | ~Q(phone=""),
                name="accounts_user_guest_requires_contact",
            ),
            # Database backstop for the tier flex rule in clean(): no tier means
            # no flex, otherwise the flex range must stay on the SkillTier scale.
            models.CheckConstraint(
                condition=Q(skill_tier__isnull=True, tier_flex_down=0, tier_flex_up=0)
                | Q(
                    # Explicit: NULL comparisons are unknown, which CHECK passes.
                    skill_tier__isnull=False,
                    skill_tier__gte=F("tier_flex_down") + MIN_TIER,
                    skill_tier__lte=MAX_TIER - F("tier_flex_up"),
                ),
                name="accounts_user_tier_flex_within_scale",
                violation_error_message=(
                    "Tier range must stay between Beginner and Elite."
                ),
            ),
        ]

    def __str__(self):
        return self.display_name or self.email or str(self.id)

    def clean_fields(self, exclude=None):
        # Normalize before field validators run, so " A@B.com " validates.
        self.email = normalize_email_address(self.email)
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        # Field-keyed errors make full_clean() skip the matching constraints,
        # so users see these messages rather than generic constraint ones.
        errors = {}
        if self.account_type == AccountType.FULL and self.email is None:
            errors["email"] = "Full accounts require an email address."
        errors.update(self._tier_flex_errors())
        if errors:
            raise ValidationError(errors)

    def _tier_flex_errors(self):
        down, up = self.tier_flex_down, self.tier_flex_up
        if down is None or up is None:
            return {}  # Already reported by clean_fields().

        if self.skill_tier is None:
            if down or up:
                return {"skill_tier": "Choose your skill tier before setting a range."}
            return {}
        if self.skill_tier not in SkillTier.values:
            return {}  # Already reported by clean_fields().

        tier = SkillTier(self.skill_tier)
        errors = {}
        if tier - down < MIN_TIER:
            errors["tier_flex_down"] = (
                f"From {tier.label} you can go at most {tier - MIN_TIER} tier(s) down."
            )
        if tier + up > MAX_TIER:
            errors["tier_flex_up"] = (
                f"From {tier.label} you can go at most {MAX_TIER - tier} tier(s) up."
            )
        return errors

    def save(self, *args, **kwargs):
        self.email = normalize_email_address(self.email)
        super().save(*args, **kwargs)

    @property
    def is_guest(self):
        return self.account_type == AccountType.GUEST

    @property
    def is_onboarded(self):
        """Full accounts are onboarded once skill tier and gender are set."""
        return (
            self.account_type == AccountType.FULL
            and self.skill_tier is not None
            and bool(self.gender)
        )
