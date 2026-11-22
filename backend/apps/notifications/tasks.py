from celery import shared_task

from .models import Notification
from .services import (
    NotificationDeferred,
    RetryableNotificationError,
    deliver_notification,
)


def _deliver(task, notification_id, expected_kind):
    try:
        return deliver_notification(
            notification_id=notification_id,
            expected_kind=expected_kind,
        )
    except (NotificationDeferred, RetryableNotificationError) as exc:
        raise task.retry(
            exc=exc,
            countdown=exc.retry_after,
        ) from exc


@shared_task(
    bind=True,
    name="notifications.send_notification",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=30,
)
def send_notification_task(self, notification_id):
    return _deliver(
        self,
        notification_id,
        Notification.Kind.NOTIFICATION,
    )


@shared_task(
    bind=True,
    name="notifications.send_reminder",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=30,
)
def send_reminder_task(self, notification_id):
    return _deliver(
        self,
        notification_id,
        Notification.Kind.REMINDER,
    )
