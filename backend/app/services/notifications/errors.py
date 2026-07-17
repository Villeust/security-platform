class NotificationDomainError(ValueError):
    """Controlled notification-domain validation failure."""


class NotificationTemplateImmutableError(NotificationDomainError):
    """Raised when published template content is mutated in place."""
