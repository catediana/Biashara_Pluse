import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import (
    PermanentNotificationError,
    RetryableNotificationError,
    deliver_notification,
    queue_notification,
)
from apps.organisations.models import Organisation
from core.exceptions import ConflictError


@pytest.mark.django_db
def test_notification_outbox_is_idempotent_and_delivery_sends_once(monkeypatch):
    organisation = Organisation.objects.create(
        name="Notification tenant",
        sector=Organisation.Sector.RETAIL,
    )
    monkeypatch.setattr(
        "apps.notifications.services._enqueue",
        lambda *args: None,
    )
    key = uuid.uuid4()
    payload = {
        "organisation": organisation,
        "channel": Notification.Channel.EMAIL,
        "recipient": "cashier@example.com",
        "subject": "Daily summary",
        "message": "Your report is ready.",
        "idempotency_key": key,
    }
    notification, created = queue_notification(**payload)
    duplicate, duplicate_created = queue_notification(**payload)
    assert created is True
    assert duplicate_created is False
    assert duplicate.pk == notification.pk
    assert Notification.objects.for_organisation(organisation).count() == 1

    calls = []

    def send(**kwargs):
        calls.append(kwargs)
        return "provider-message-1"

    monkeypatch.setattr("apps.notifications.services.send_via_channel", send)
    first = deliver_notification(
        notification_id=notification.pk,
        expected_kind=Notification.Kind.NOTIFICATION,
    )
    duplicate_delivery = deliver_notification(
        notification_id=notification.pk,
        expected_kind=Notification.Kind.NOTIFICATION,
    )
    notification.refresh_from_db()
    assert first["status"] == Notification.Status.SENT
    assert duplicate_delivery["status"] == Notification.Status.SENT
    assert len(calls) == 1
    assert notification.attempts == 1
    assert notification.provider_message_id == "provider-message-1"


@pytest.mark.django_db
def test_notification_retries_transient_errors_and_marks_permanent_failure(
    monkeypatch,
):
    organisation = Organisation.objects.create(
        name="Retry tenant",
        sector=Organisation.Sector.RETAIL,
    )
    monkeypatch.setattr(
        "apps.notifications.services._enqueue",
        lambda *args: None,
    )
    notification, _ = queue_notification(
        organisation=organisation,
        channel=Notification.Channel.SMS,
        recipient="+254712345678",
        message="Your payment is due.",
        idempotency_key=uuid.uuid4(),
    )

    def temporary_failure(**_kwargs):
        from apps.integrations.messaging import ProviderDeliveryError

        raise ProviderDeliveryError("Provider busy.", retryable=True)

    monkeypatch.setattr(
        "apps.notifications.services.send_via_channel",
        temporary_failure,
    )
    with pytest.raises(RetryableNotificationError):
        deliver_notification(
            notification_id=notification.pk,
            expected_kind=Notification.Kind.NOTIFICATION,
        )
    notification.refresh_from_db()
    assert notification.status == Notification.Status.PENDING
    assert notification.attempts == 1
    assert notification.next_attempt_at is not None

    notification.next_attempt_at = None
    notification.save(update_fields=["next_attempt_at", "updated_at"])

    def permanent_failure(**_kwargs):
        from apps.integrations.messaging import ProviderDeliveryError

        raise ProviderDeliveryError("Invalid recipient.", retryable=False)

    monkeypatch.setattr(
        "apps.notifications.services.send_via_channel",
        permanent_failure,
    )
    with pytest.raises(PermanentNotificationError):
        deliver_notification(
            notification_id=notification.pk,
            expected_kind=Notification.Kind.NOTIFICATION,
        )
    notification.refresh_from_db()
    assert notification.status == Notification.Status.FAILED
    assert notification.attempts == 2


@pytest.mark.django_db
def test_notification_key_cannot_be_reused_for_different_content(monkeypatch):
    organisation = Organisation.objects.create(
        name="Conflict tenant",
        sector=Organisation.Sector.RETAIL,
    )
    monkeypatch.setattr(
        "apps.notifications.services._enqueue",
        lambda *args: None,
    )
    key = uuid.uuid4()
    queue_notification(
        organisation=organisation,
        channel=Notification.Channel.SMS,
        recipient="+254712345678",
        message="Reminder A",
        idempotency_key=key,
    )
    with pytest.raises(ConflictError):
        queue_notification(
            organisation=organisation,
            channel=Notification.Channel.SMS,
            recipient="+254712345678",
            message="Reminder B",
            idempotency_key=key,
        )


@pytest.mark.django_db(transaction=True)
def test_scheduled_reminder_uses_future_delivery_time(monkeypatch):
    organisation = Organisation.objects.create(
        name="Reminder tenant",
        sector=Organisation.Sector.RETAIL,
    )
    scheduled_at = timezone.now() + timedelta(days=1)
    enqueued = []
    monkeypatch.setattr(
        "apps.notifications.services._enqueue",
        lambda *args: enqueued.append(args),
    )
    notification, created = queue_notification(
        organisation=organisation,
        kind=Notification.Kind.REMINDER,
        channel=Notification.Channel.WHATSAPP,
        recipient="254712345678",
        message="Your appointment is tomorrow.",
        idempotency_key=uuid.uuid4(),
        scheduled_at=scheduled_at,
    )
    assert created is True
    assert notification.kind == Notification.Kind.REMINDER
    assert enqueued == [(notification.pk, Notification.Kind.REMINDER, scheduled_at)]
