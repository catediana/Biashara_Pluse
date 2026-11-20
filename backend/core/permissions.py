from rest_framework.permissions import BasePermission


class HasActiveOrganisation(BasePermission):
    message = "An active organisation is required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(request, "active_organisation", None) is not None
        )
