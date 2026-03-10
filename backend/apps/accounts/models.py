"""
Account models: User, Organization, Team, and BillingRate.
"""

import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager supporting email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class Organization(models.Model):
    """
    Organization is the top-level tenant.
    All data is scoped to an organization.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    logo = models.ImageField(upload_to="org_logos/", blank=True, null=True)
    website = models.URLField(blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    tax_id = models.CharField(max_length=50, blank=True, default="", help_text="Tax identification number")
    default_currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        default=1,
        help_text="Month when fiscal year starts (1=January)",
    )
    default_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    overtime_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.50
    )
    work_hours_per_day = models.DecimalField(
        max_digits=4, decimal_places=2, default=8.00
    )
    work_days_per_week = models.PositiveSmallIntegerField(default=5)
    invoice_prefix = models.CharField(max_length=10, default="INV")
    invoice_next_number = models.PositiveIntegerField(default=1001)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_next_invoice_number(self):
        """Generate and increment the next invoice number."""
        number = f"{self.invoice_prefix}-{self.invoice_next_number:05d}"
        self.invoice_next_number += 1
        self.save(update_fields=["invoice_next_number"])
        return number


class User(AbstractUser):
    """
    Custom User model using email for authentication.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Remove username field
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    job_title = models.CharField(max_length=100, blank=True, default="")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.MEMBER
    )
    timezone = models.CharField(max_length=50, default="UTC")
    default_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="User's default cost rate for profitability calculations",
    )
    is_billable = models.BooleanField(
        default=True,
        help_text="Whether this user's time is billable by default",
    )
    weekly_capacity_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=40.00,
        help_text="Expected weekly working hours for utilization calculations",
    )
    date_joined = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def is_org_admin(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)

    def is_manager_or_above(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.MANAGER)


class Team(models.Model):
    """
    Teams within an organization for grouping members.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    lead = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_teams",
    )
    members = models.ManyToManyField(User, related_name="teams", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["organization", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class BillingRate(models.Model):
    """
    Flexible billing rates that can be set at various levels:
    organization, user, project, or user+project combination.
    """

    class RateType(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        FIXED = "fixed", "Fixed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="billing_rates"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="billing_rates",
        null=True,
        blank=True,
        help_text="If set, this rate applies to this specific user",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="billing_rates",
        null=True,
        blank=True,
        help_text="If set, this rate applies to this specific project",
    )
    rate_type = models.CharField(
        max_length=10, choices=RateType.choices, default=RateType.HOURLY
    )
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        target = self.user or self.project or self.organization
        return f"{target} - {self.rate_type}: {self.currency} {self.rate}"

    @classmethod
    def get_effective_rate(cls, organization, user=None, project=None, date=None):
        """
        Get the most specific applicable billing rate.
        Priority: user+project > project > user > organization default.
        """
        if date is None:
            date = timezone.now().date()

        filters = {
            "organization": organization,
            "is_active": True,
            "effective_from__lte": date,
        }

        # Try user+project specific rate
        if user and project:
            rate = cls.objects.filter(
                **filters, user=user, project=project
            ).filter(
                models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
            ).first()
            if rate:
                return rate

        # Try project specific rate
        if project:
            rate = cls.objects.filter(
                **filters, project=project, user__isnull=True
            ).filter(
                models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
            ).first()
            if rate:
                return rate

        # Try user specific rate
        if user:
            rate = cls.objects.filter(
                **filters, user=user, project__isnull=True
            ).filter(
                models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
            ).first()
            if rate:
                return rate

        # Fallback: organization default rate
        rate = cls.objects.filter(
            **filters, user__isnull=True, project__isnull=True
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
        ).first()
        return rate
