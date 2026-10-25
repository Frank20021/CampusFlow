"""Event names and channel naming for the real-time layer."""

from uuid import UUID

MESSAGE_CREATED = "message.created"
MESSAGE_DELETED = "message.deleted"
NOTIFICATION_CREATED = "notification.created"
PING = "ping"


def group_channel(group_id: UUID) -> str:
    """One pub/sub channel per group.

    Chosen: a channel per group so a worker only receives traffic for groups
    it actually has listeners for. Alternative: one global channel with
    server-side filtering — simpler, but every worker would wake up for every
    message in the product.
    """
    return f"campusflow:group:{group_id}:events"


def user_channel(user_id: UUID) -> str:
    """One channel per student for their inbox.

    Group events stay on the group channel; a notification is personal, so it
    fans out here instead. A worker with no listener for this user never
    wakes up.
    """
    return f"campusflow:user:{user_id}:events"
