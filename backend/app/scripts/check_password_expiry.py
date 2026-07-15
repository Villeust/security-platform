from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.admin import AdminNotificationSeverity, AdminNotificationType, AuthSource, User
from app.models.reference_data import utc_now
from app.services.notification_service import create_notification
from app.services.password_service import password_expiry_info


def run() -> int:
    updated = 0
    with SessionLocal() as db:
        users = db.scalars(
            select(User).where(
                User.auth_source == AuthSource.LOCAL,
                User.authentication_enabled.is_(True),
                User.is_active.is_(True),
            )
        ).all()
        for user in users:
            info = password_expiry_info(user.password_expires_at)
            if info.expired and user.password_expired_at is None:
                user.password_expired_at = utc_now()
                user.must_change_password = True
                create_notification(
                    db,
                    AdminNotificationType.PASSWORD_EXPIRED,
                    AdminNotificationSeverity.HIGH,
                    "Срок действия пароля истёк",
                    f"Пользователь {user.username} должен сменить локальный пароль.",
                    user_id=user.id,
                )
                updated += 1
            elif info.warning and user.password_expiry_notified_at is None:
                user.password_expiry_notified_at = utc_now()
                create_notification(
                    db,
                    AdminNotificationType.PASSWORD_EXPIRING,
                    AdminNotificationSeverity.WARNING,
                    "Срок действия пароля скоро истечёт",
                    f"Пользователю {user.username} нужно сменить пароль в ближайшие дни.",
                    user_id=user.id,
                    details={"days_remaining": info.days_remaining},
                )
                updated += 1
        db.commit()
    return updated


if __name__ == "__main__":
    count = run()
    print(f"Password expiry check completed. Updated users: {count}")
