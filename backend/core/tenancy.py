import uuid

from django.core.exceptions import PermissionDenied
from django.db import models


def get_active_organisation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")

    organisation = getattr(request, "active_organisation", None)
    if organisation is None or not getattr(organisation, "is_active", False):
        raise PermissionDenied("An active organisation is required.")

    return organisation


def get_active_membership(request):
    user = getattr(request, "user", None)
    organisation = getattr(request, "active_organisation", None)
    if (
        user is None
        or not user.is_authenticated
        or organisation is None
        or not getattr(organisation, "is_active", False)
    ):
        return None

    from apps.organisations.models import Membership

    membership = getattr(request, "active_membership", None)
    if (
        membership is not None
        and membership.user_id == user.pk
        and membership.organisation_id == organisation.pk
        and membership.status == Membership.Status.ACTIVE
        and membership.role.is_active
        and membership.role.organisation_id == organisation.pk
    ):
        return membership

    return (
        Membership.objects.select_related("role")
        .filter(
            user=user,
            user__is_active=True,
            organisation_id=organisation.pk,
            status=Membership.Status.ACTIVE,
            role__organisation_id=organisation.pk,
            role__is_active=True,
        )
        .first()
    )


class TenantQuerySet(models.QuerySet):
    def for_organisation(self, organisation):
        if organisation is None:
            raise ValueError("An organisation is required to scope tenant data.")
        organisation_id = getattr(organisation, "pk", organisation)
        return self.filter(organisation_id=organisation_id)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def for_organisation(self, organisation):
        return self.get_queryset().for_organisation(organisation)


class TenantModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="%(class)s_set",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        abstract = True


def scope_queryset(queryset, organisation):
    if organisation is None:
        raise ValueError("An organisation is required to scope tenant data.")
    if hasattr(queryset, "for_organisation"):
        return queryset.for_organisation(organisation)
    return queryset.filter(organisation=organisation)
