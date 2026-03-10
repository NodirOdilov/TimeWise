"""
Serializers for the accounts app.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Organization, Team, BillingRate

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer that includes user info in response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "logo", "website",
            "address_line1", "address_line2", "city", "state",
            "postal_code", "country", "phone", "tax_id",
            "default_currency", "fiscal_year_start_month",
            "default_hourly_rate", "overtime_multiplier",
            "work_hours_per_day", "work_days_per_week",
            "invoice_prefix", "invoice_next_number",
            "is_active", "member_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "member_count"]

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "name", "slug", "website", "default_currency",
            "default_hourly_rate", "work_hours_per_day",
        ]


class UserSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "avatar", "phone", "job_title", "organization",
            "organization_name", "role", "timezone",
            "default_hourly_rate", "is_billable",
            "weekly_capacity_hours", "date_joined", "last_activity",
        ]
        read_only_fields = [
            "id", "email", "date_joined", "last_activity",
            "organization_name", "full_name",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "email", "password", "password_confirm",
            "first_name", "last_name", "phone", "job_title",
            "timezone",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(**validated_data)
        return user


class RegisterSerializer(serializers.Serializer):
    """Registration serializer that creates a user and optionally an organization."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    organization_name = serializers.CharField(required=False, max_length=255)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        org_name = validated_data.pop("organization_name", None)
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        organization = None
        if org_name:
            slug = org_name.lower().replace(" ", "-")[:100]
            # Ensure unique slug
            base_slug = slug
            counter = 1
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            organization = Organization.objects.create(name=org_name, slug=slug)

        user = User.objects.create_user(
            email=validated_data["email"],
            password=password,
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            organization=organization,
            role=User.Role.OWNER if organization else User.Role.MEMBER,
        )
        return user


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "phone", "job_title",
            "avatar", "timezone", "weekly_capacity_hours",
        ]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs


class TeamSerializer(serializers.ModelSerializer):
    lead_name = serializers.CharField(source="lead.full_name", read_only=True)
    member_count = serializers.SerializerMethodField()
    members_detail = UserSerializer(source="members", many=True, read_only=True)

    class Meta:
        model = Team
        fields = [
            "id", "organization", "name", "description",
            "lead", "lead_name", "members", "members_detail",
            "member_count", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def get_member_count(self, obj):
        return obj.members.count()


class BillingRateSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = BillingRate
        fields = [
            "id", "organization", "user", "user_name",
            "project", "project_name", "rate_type", "rate",
            "currency", "effective_from", "effective_to",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]
