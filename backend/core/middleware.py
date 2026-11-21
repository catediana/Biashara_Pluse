from uuid import UUID

from apps.organisations.models import Membership


class ActiveOrganisationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_organisation = None
        request.active_membership = None

        user = getattr(request, "user", None)
        organisation_id = request.headers.get("X-Organisation-ID")
        if user is not None and user.is_authenticated and user.is_active:
            try:
                organisation_id = UUID(organisation_id)
            except (TypeError, ValueError, AttributeError):
                organisation_id = None

            if organisation_id is not None:
                membership = (
                    Membership.objects.select_related("organisation", "role")
                    .filter(
                        organisation_id=organisation_id,
                        organisation__is_active=True,
                        user=user,
                        status=Membership.Status.ACTIVE,
                        role__organisation_id=organisation_id,
                        role__is_active=True,
                    )
                    .first()
                )
                if membership is not None:
                    request.active_organisation = membership.organisation
                    request.active_membership = membership

        return self.get_response(request)
