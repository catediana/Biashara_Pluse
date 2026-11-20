from django.core.exceptions import PermissionDenied


def get_active_organisation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")

    organisation = getattr(request, "active_organisation", None)
    if organisation is None:
        raise PermissionDenied("An active organisation is required.")

    return organisation


def scope_queryset(queryset, organisation):
    if organisation is None:
        raise ValueError("An organisation is required to scope tenant data.")
    return queryset.filter(organisation=organisation)
