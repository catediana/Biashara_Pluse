from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.tenancy import TenantModel


class Notification(TenantModel):
    class Kind(models.TextChoices):
        NOTIFICATION = "notification", "Notification"
        REMINDER = "reminder", "Reminder"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.NOTIFICATION,
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    recipient = models.CharField(max_length=254)
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )
    scheduled_at = models.DateTimeField(default=timezone.now)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_notification_idem_org",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "status", "scheduled_at"],
                name="notify_org_status_sched_idx",
            ),
            models.Index(
                fields=["status", "lease_expires_at"],
                name="notify_status_lease_idx",
            ),
        ]
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.channel == self.Channel.EMAIL:
            EmailValidator()(self.recipient)
            if not self.subject.strip():
                raise ValidationError({"subject": "Email notifications require a subject."})
        if not self.message.strip():
            raise ValidationError({"message": "Notification message cannot be blank."})
        if self.status == self.Status.SENDING and self.lease_expires_at is None:
            raise ValidationError(
                {"lease_expires_at": "Sending notifications require a lease expiry."}
            )
        if self.status == self.Status.SENT and self.sent_at is None:
            raise ValidationError(
                {"sent_at": "Sent notifications require a sent time."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous is not None and (
                previous.kind != self.kind
                or previous.channel != self.channel
                or previous.recipient != self.recipient
                or previous.subject != self.subject
                or previous.message != self.message
                or previous.idempotency_key != self.idempotency_key
                or previous.request_fingerprint != self.request_fingerprint
                or previous.organisation_id != self.organisation_id
            ):
                raise ValidationError(
                    "Notification delivery details are immutable."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Notification outbox records cannot be deleted.")
