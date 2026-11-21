import uuid

from django.core.exceptions import ValidationError
from django.db import models

from core.tenancy import TenantModel


class Role(TenantModel):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(
        "rbac.Permission",
        through="rbac.RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_role_name_per_org",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "is_active"],
                name="role_org_active_idx",
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Permission(models.Model):
    class Module(models.TextChoices):
        PLATFORM = "platform", "Platform"
        RETAIL = "retail", "Retail"
        WHOLESALE = "wholesale", "Wholesale"
        SCHOOLS = "schools", "Schools"
        PHARMACY = "pharmacy", "Pharmacy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=120)
    module = models.CharField(
        max_length=20,
        choices=Module.choices,
        default=Module.PLATFORM,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "codename"]

    def __str__(self):
        return self.codename


class RolePermission(TenantModel):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name="role_permissions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "role", "permission"],
                name="uniq_org_role_permission",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "role"],
                name="roleperm_org_role_idx",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.role_id
            and self.organisation_id
            and self.role.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"role": "The role must belong to this organisation."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class BranchGrant(TenantModel):
    membership = models.ForeignKey(
        "organisations.Membership",
        on_delete=models.CASCADE,
        related_name="branch_grants",
    )
    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.CASCADE,
        related_name="membership_grants",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "membership", "branch"],
                name="uniq_org_membership_branch",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "membership"],
                name="branchgrant_org_member_idx",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.membership_id
            and self.organisation_id
            and self.membership.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"membership": "The membership must belong to this organisation."}
            )
        if (
            self.branch_id
            and self.organisation_id
            and self.branch.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"branch": "The branch must belong to this organisation."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
