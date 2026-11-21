from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from apps.billing.models import ModuleEntitlement
from apps.organisations.models import Branch
from apps.rbac.models import BranchGrant, RolePermission
from core.tenancy import get_active_membership


def _active_organisation(request):
    organisation = getattr(request, "active_organisation", None)
    if organisation is None or not getattr(organisation, "is_active", False):
        return None
    return organisation


def _requested_branch_id(request, view):
    kwargs = getattr(view, "kwargs", {})
    for key in ("branch_pk", "branch_id", "branch"):
        value = kwargs.get(key)
        if value is not None:
            return value

    for source_name in ("query_params", "data"):
        source = getattr(request, source_name, {})
        for key in ("branch_id", "branch"):
            value = source.get(key)
            if value is not None:
                return value
    return None


def _membership_has_branch(membership, organisation, branch_id):
    branch_exists = Branch.objects.for_organisation(organisation).filter(
        pk=branch_id,
        is_active=True,
    ).exists()
    if not branch_exists:
        return False
    if membership.all_branches:
        return True
    return BranchGrant.objects.for_organisation(organisation).filter(
        membership=membership,
        membership__organisation_id=organisation.pk,
        branch_id=branch_id,
        branch__organisation_id=organisation.pk,
    ).exists()


class HasMembership(BasePermission):
    message = "An active membership in the selected organisation is required."

    def has_permission(self, request, _view):
        return get_active_membership(request) is not None


class HasActiveOrganisation(HasMembership):
    pass


class HasRolePermission(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        permission_code = getattr(view, "required_permission", None)
        organisation = _active_organisation(request)
        if membership is None or permission_code is None or organisation is None:
            return False

        permissions = RolePermission.objects.for_organisation(organisation).filter(
            role_id=membership.role_id,
            role__organisation_id=organisation.pk,
            role__is_active=True,
            permission__codename=permission_code,
            permission__is_active=True,
        )
        required_module = getattr(view, "required_module", None)
        if required_module is not None:
            permissions = permissions.filter(permission__module=required_module)
        return permissions.exists()


class HasBranchAccess(BasePermission):
    message = "You do not have access to the selected branch."

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        organisation = _active_organisation(request)
        if membership is None or organisation is None:
            return False

        branch_id = _requested_branch_id(request, view)
        if branch_id is None:
            if membership.all_branches:
                return True
            return bool(
                getattr(view, "branch_object_lookup", False)
                and getattr(view, "kwargs", {}).get("pk") is not None
            )
        return _membership_has_branch(membership, organisation, branch_id)

    def has_object_permission(self, request, _view, obj):
        membership = get_active_membership(request)
        organisation = _active_organisation(request)
        if membership is None or organisation is None:
            return False

        if isinstance(obj, Branch):
            branch_id = obj.pk
        else:
            branch_id = getattr(obj, "branch_id", None)
            if branch_id is None:
                branch = getattr(obj, "branch", None)
                branch_id = getattr(branch, "pk", None)
        if branch_id is None:
            return False
        return _membership_has_branch(membership, organisation, branch_id)


class HasModuleEntitlement(BasePermission):
    message = "The selected module is not enabled for this organisation."

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        organisation = _active_organisation(request)
        module = getattr(view, "required_module", None)
        if membership is None or organisation is None or module is None:
            return False

        now = timezone.now()
        return ModuleEntitlement.objects.for_organisation(organisation).filter(
            module=module,
            is_enabled=True,
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        ).exists()


class HasTenantAccess(BasePermission):
    message = "You do not have access to this organisation resource."

    def has_permission(self, request, view):
        if not HasMembership().has_permission(request, view):
            return False
        if not HasRolePermission().has_permission(request, view):
            return False

        required_module = getattr(view, "required_module", None)
        if required_module and not HasModuleEntitlement().has_permission(
            request, view
        ):
            return False

        if getattr(view, "branch_scoped", False):
            return HasBranchAccess().has_permission(request, view)
        return True

    def has_object_permission(self, request, view, obj):
        if not HasMembership().has_permission(request, view):
            return False
        if not HasRolePermission().has_permission(request, view):
            return False

        required_module = getattr(view, "required_module", None)
        if required_module and not HasModuleEntitlement().has_permission(
            request, view
        ):
            return False

        if getattr(view, "branch_scoped", False):
            return HasBranchAccess().has_object_permission(request, view, obj)
        return True
