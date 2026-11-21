import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.audit import redact_audit_metadata
from core.tenancy import TenantModel


class AuditEvent(TenantModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    reason = models.CharField(max_length=255, blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(
                fields=["organisation", "created_at"],
                name="audit_org_created_idx",
            ),
            models.Index(
                fields=["organisation", "action", "created_at"],
                name="audit_org_action_idx",
            ),
        ]
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit events are immutable.")
        self.metadata = redact_audit_metadata(self.metadata)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events cannot be deleted.")
