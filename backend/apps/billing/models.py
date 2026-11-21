from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.tenancy import TenantModel


class ModuleEntitlement(TenantModel):
    class Module(models.TextChoices):
        RETAIL = "retail", "Retail"
        WHOLESALE = "wholesale", "Wholesale"
        SCHOOLS = "schools", "Schools"
        PHARMACY = "pharmacy", "Pharmacy"

    module = models.CharField(max_length=20, choices=Module.choices)
    is_enabled = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "module"],
                name="uniq_org_module_entitlement",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "module", "is_enabled"],
                name="entitle_org_module_idx",
            )
        ]

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError(
                {"ends_at": "Entitlement end must be later than its start."}
            )

    def is_active_at(self, at=None):
        at = at or timezone.now()
        return (
            self.is_enabled
            and (self.starts_at is None or self.starts_at <= at)
            and (self.ends_at is None or self.ends_at > at)
        )
