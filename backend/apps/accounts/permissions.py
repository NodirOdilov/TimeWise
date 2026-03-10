"""
Custom permissions for the accounts app.
"""

from rest_framework import permissions


class IsOrganizationOwner(permissions.BasePermission):
    """
    Only allow organization owners to perform the action.
    """

    message = "Only organization owners can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == request.user.Role.OWNER


class IsOrganizationAdmin(permissions.BasePermission):
    """
    Allow organization owners and admins.
    """

    message = "Only organization admins can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_org_admin()


class IsManagerOrAbove(permissions.BasePermission):
    """
    Allow managers, admins, and owners.
    """

    message = "Only managers and above can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_manager_or_above()


class IsSameOrganization(permissions.BasePermission):
    """
    Ensure the user belongs to the same organization as the
    resource being accessed.
    """

    message = "You can only access resources within your organization."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        org = getattr(obj, "organization", None)
        if org is None:
            org = getattr(obj, "organization_id", None)
            if org is None:
                return True
            return str(org) == str(request.user.organization_id)
        return org == request.user.organization


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow full access to the resource owner, read-only for others.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner_field = getattr(view, "owner_field", "user")
        return getattr(obj, owner_field, None) == request.user


class IsOwnerOrManager(permissions.BasePermission):
    """
    Allow access to the resource owner or managers and above.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_manager_or_above():
            return True
        owner_field = getattr(view, "owner_field", "user")
        return getattr(obj, owner_field, None) == request.user


class CanManageTeam(permissions.BasePermission):
    """
    Allow team leads, admins, and owners to manage teams.
    """

    message = "Only team leads, admins, and owners can manage teams."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_org_admin():
            return True
        return obj.lead == request.user


class CanApproveTimeEntries(permissions.BasePermission):
    """
    Only managers and above can approve time entries.
    """

    message = "Only managers can approve or reject time entries."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_manager_or_above()


class CanManageInvoices(permissions.BasePermission):
    """
    Only admins and owners can create/edit invoices.
    """

    message = "Only admins and owners can manage invoices."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_manager_or_above()
        return request.user.is_org_admin()


class CanViewReports(permissions.BasePermission):
    """
    Managers and above can view all reports.
    Members can only view their own reports.
    """

    message = "You do not have permission to view these reports."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_manager_or_above():
            return True
        user_field = getattr(obj, "user", None)
        if user_field:
            return user_field == request.user
        return False
