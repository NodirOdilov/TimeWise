"""
Views for the accounts app.
"""

from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Organization, Team, BillingRate
from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
    UserProfileUpdateSerializer,
    ChangePasswordSerializer,
    OrganizationSerializer,
    OrganizationCreateSerializer,
    TeamSerializer,
    BillingRateSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom login view that returns user info alongside tokens."""

    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """Register a new user and optionally create an organization."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """Logout by blacklisting the refresh token."""

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """View and update the current user's profile."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserProfileUpdateSerializer
        return UserSerializer


class ChangePasswordView(APIView):
    """Change the current user's password."""

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD operations for organizations."""

    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.filter(
            id=self.request.user.organization_id
        )

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def perform_create(self, serializer):
        org = serializer.save()
        self.request.user.organization = org
        self.request.user.role = User.Role.OWNER
        self.request.user.save(update_fields=["organization", "role"])

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """List all members of the organization."""
        org = self.get_object()
        members = User.objects.filter(organization=org, is_active=True)
        serializer = UserSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def invite_member(self, request, pk=None):
        """Invite a new member to the organization."""
        org = self.get_object()
        email = request.data.get("email")
        role = request.data.get("role", User.Role.MEMBER)

        if not email:
            return Response(
                {"email": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email=email, organization=org).exists():
            return Response(
                {"email": "User is already a member."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user already exists
        try:
            user = User.objects.get(email=email)
            user.organization = org
            user.role = role
            user.save(update_fields=["organization", "role"])
        except User.DoesNotExist:
            # In production, send invitation email instead
            user = User.objects.create_user(
                email=email,
                password=User.objects.make_random_password(),
                first_name=request.data.get("first_name", ""),
                last_name=request.data.get("last_name", ""),
                organization=org,
                role=role,
            )

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class TeamViewSet(viewsets.ModelViewSet):
    """CRUD operations for teams."""

    serializer_class = TeamSerializer

    def get_queryset(self):
        return Team.objects.filter(
            organization=self.request.user.organization
        ).select_related("lead").prefetch_related("members")

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        """Add a member to the team."""
        team = self.get_object()
        user_id = request.data.get("user_id")
        try:
            user = User.objects.get(
                id=user_id, organization=request.user.organization
            )
            team.members.add(user)
            return Response(
                TeamSerializer(team).data,
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"user_id": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        """Remove a member from the team."""
        team = self.get_object()
        user_id = request.data.get("user_id")
        try:
            user = User.objects.get(id=user_id)
            team.members.remove(user)
            return Response(
                TeamSerializer(team).data,
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"user_id": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


class BillingRateViewSet(viewsets.ModelViewSet):
    """CRUD operations for billing rates."""

    serializer_class = BillingRateSerializer

    def get_queryset(self):
        queryset = BillingRate.objects.filter(
            organization=self.request.user.organization
        ).select_related("user", "project")

        user_id = self.request.query_params.get("user_id")
        project_id = self.request.query_params.get("project_id")

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
