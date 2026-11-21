import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from core.tenancy import TenantModel


class Organisation(models.Model):
    class Sector(models.TextChoices):
        RETAIL = "retail", "Retail"
        WHOLESALE = "wholesale", "Wholesale"
        SCHOOLS = "schools", "Schools"
        PHARMACY = "pharmacy", "Pharmacy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    sector = models.CharField(max_length=20, choices=Sector.choices)
    country_code = models.CharField(max_length=2, default="KE")
    currency = models.CharField(max_length=3, default="KES")
    timezone = models.CharField(max_length=64, default="Africa/Nairobi")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or str(uuid.uuid4())
        super().save(*args, **kwargs)


class Branch(TenantModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_branch_name_per_org",
            ),
            models.UniqueConstraint(
                fields=["organisation", "code"],
                condition=~models.Q(code=""),
                name="uniq_branch_code_per_org",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "is_active"],
                name="branch_org_active_idx",
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TenantModel):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organisation_memberships",
    )
    role = models.ForeignKey(
        "rbac.Role",
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.INVITED,
    )
    all_branches = models.BooleanField(default=False)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "user"],
                name="uniq_org_user_membership",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "status"],
                name="membership_org_status_idx",
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

    def __str__(self):
        return f"{self.user} @ {self.organisation}"
