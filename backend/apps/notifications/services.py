import hashlib
import json
import math
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.integrations.messaging import ProviderDeliveryError, send_via_channel
from core.exceptions import ConflictError

from .models import Notification


MAX_DELIVERY_ATTEMPTS = 5
LEASE_DURATION = timedelta(minutes=5)
BASE_RETRY_SECONDS = 15
MAX_RETRY_SECONDS = 60 * 60


class RetryableNotificationError(Exception):
    def __init__(self, message, *, retry_after):
        super().__init__(message)
        self.retry_after = retry_after


class NotificationDeferred(Exception):
    def __init__(self, retry_after):
        super().__init__("Notification is not ready for delivery.")
        self.retry_after = max(1, retry_after)


class PermanentNotificationError(Exception):
    pass


def _fingerprint(*, kind, channel, recipient, subject, message, scheduled_at):
    payload = {
        "kind": kind,
        "channel": channel,
        "recipient": recipient,
        "subject": subject,
        "message": message,
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _enqueue(notification_id, kind, available_at):
    from .tasks import send_notification_task, send_reminder_task

    task = (
        send_reminder_task
        if kind == Notification.Kind.REMINDER
        else send_notification_task
    )
    kwargs = {"args": [str(notification_id)]}
    if available_at > timezone.now():
        kwargs["eta"] = available_at
    task.apply_async(**kwargs)


def _schedule_delivery(notification):
    if notification.status in (
        Notification.Status.SENT,
        Notification.Status.FAILED,
    ):
        return
    available_at = notification.scheduled_at
    for candidate in (
        notification.next_attempt_at,
        notification.lease_expires_at,
    ):
        if candidate is not None:
            available_at = max(available_at, candidate)
    transaction.on_commit(
        lambda: _enqueue(
            notification.pk,
            notification.kind,
            available_at,
        )
    )


def queue_notification(
    *,
    organisation,
    kind=Notification.Kind.NOTIFICATION,
    channel,
    recipient,
    message,
    subject="",
    idempotency_key,
    scheduled_at=None,
):
    requested_schedule = scheduled_at
    scheduled_at = scheduled_at or timezone.now()
    fingerprint = _fingerprint(
        kind=kind,
        channel=channel,
        recipient=recipient,
        subject=subject,
        message=message,
        scheduled_at=requested_schedule,
    )
    try:
        with transaction.atomic():
            existing = (
                Notification.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ConflictError(
                        "This idempotency key was already used for another notification."
                    )
                _schedule_delivery(existing)
                return existing, False
            notification = Notification.objects.create(
                organisation=organisation,
                kind=kind,
                channel=channel,
                recipient=recipient,
                subject=subject,
                message=message,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                scheduled_at=scheduled_at,
            )
            _schedule_delivery(notification)
            return notification, True
    except IntegrityError:
        existing = (
            Notification.objects.for_organisation(organisation)
            .filter(idempotency_key=idempotency_key)
            .first()
        )
        if existing is None:
            raise
        if existing.request_fingerprint != fingerprint:
            raise ConflictError(
                "This idempotency key was already used for another notification."
            )
        _schedule_delivery(existing)
        return existing, False


def _retry_delay(attempt):
    return min(BASE_RETRY_SECONDS * (2 ** max(0, attempt - 1)), MAX_RETRY_SECONDS)


def _set_failed(notification_id, error):
    with transaction.atomic():
        notification = Notification.objects.select_for_update().get(
            pk=notification_id
        )
        notification.status = Notification.Status.FAILED
        notification.last_error = str(error)[:500]
        notification.lease_expires_at = None
        notification.next_attempt_at = None
        notification.save(
            update_fields=[
                "status",
                "last_error",
                "lease_expires_at",
                "next_attempt_at",
                "updated_at",
            ]
        )


def _set_retry(notification_id, error, delay):
    with transaction.atomic():
        notification = Notification.objects.select_for_update().get(
            pk=notification_id
        )
        notification.status = Notification.Status.PENDING
        notification.last_error = str(error)[:500]
        notification.lease_expires_at = None
        notification.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        notification.save(
            update_fields=[
                "status",
                "last_error",
                "lease_expires_at",
                "next_attempt_at",
                "updated_at",
            ]
        )


def deliver_notification(*, notification_id, expected_kind):
    with transaction.atomic():
        notification = (
            Notification.objects.select_for_update()
            .select_related("organisation")
            .filter(pk=notification_id)
            .first()
        )
        if notification is None:
            raise Notification.DoesNotExist
        if notification.kind != expected_kind:
            raise ValueError("The notification task does not match its stored kind.")
        if notification.status == Notification.Status.SENT:
            return {"status": notification.status}
        if notification.status == Notification.Status.FAILED:
            raise PermanentNotificationError(
                notification.last_error or "Notification delivery previously failed."
            )

        now = timezone.now()
        available_at = notification.scheduled_at
        if notification.next_attempt_at is not None:
            available_at = max(available_at, notification.next_attempt_at)
        if notification.status == Notification.Status.SENDING:
            if notification.lease_expires_at and notification.lease_expires_at > now:
                seconds = math.ceil(
                    (notification.lease_expires_at - now).total_seconds()
                )
                raise NotificationDeferred(seconds)
        if available_at > now:
            seconds = math.ceil((available_at - now).total_seconds())
            raise NotificationDeferred(seconds)

        notification.status = Notification.Status.SENDING
        notification.attempts += 1
        notification.lease_expires_at = now + LEASE_DURATION
        notification.save(
            update_fields=[
                "status",
                "attempts",
                "lease_expires_at",
                "updated_at",
            ]
        )

    try:
        provider_message_id = send_via_channel(
            channel=notification.channel,
            recipient=notification.recipient,
            subject=notification.subject,
            message=notification.message,
        )
    except ProviderDeliveryError as exc:
        if exc.retryable and notification.attempts < MAX_DELIVERY_ATTEMPTS:
            delay = _retry_delay(notification.attempts)
            _set_retry(notification.pk, exc, delay)
            raise RetryableNotificationError(
                str(exc),
                retry_after=delay,
            ) from exc
        _set_failed(notification.pk, exc)
        raise PermanentNotificationError(str(exc)) from exc
    except ImproperlyConfigured as exc:
        _set_failed(notification.pk, exc)
        raise PermanentNotificationError(str(exc)) from exc

    with transaction.atomic():
        stored = Notification.objects.select_for_update().get(pk=notification.pk)
        if stored.status == Notification.Status.SENT:
            return {"status": stored.status}
        stored.status = Notification.Status.SENT
        stored.sent_at = timezone.now()
        stored.provider_message_id = provider_message_id or ""
        stored.last_error = ""
        stored.lease_expires_at = None
        stored.next_attempt_at = None
        stored.save(
            update_fields=[
                "status",
                "sent_at",
                "provider_message_id",
                "last_error",
                "lease_expires_at",
                "next_attempt_at",
                "updated_at",
            ]
        )
    return {"status": Notification.Status.SENT}
