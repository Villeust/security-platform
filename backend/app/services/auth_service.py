import hashlib
import hmac
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.admin import AdminNotificationSeverity, AdminNotificationType, AuthSession, AuthSource, LockReason, User
from app.models.reference_data import utc_now
from app.services.audit_service import write_audit
from app.services.notification_service import create_notification
from app.services.password_service import password_expiry_info, password_expires_at_from_now, password_hasher, validate_password_policy

AUTH_FAILURE_DETAIL = "Неверное имя пользователя или пароль"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = settings.environment.lower() in {"production", "prod"}
    response.set_cookie(settings.auth_access_cookie_name, access_token, httponly=True, samesite="lax", secure=secure)
    response.set_cookie(settings.auth_refresh_cookie_name, refresh_token, httponly=True, samesite="lax", secure=secure)
    response.set_cookie(settings.auth_csrf_cookie_name, csrf_token, httponly=False, samesite="lax", secure=secure)


def clear_auth_cookies(response: Response) -> None:
    for name in (settings.auth_access_cookie_name, settings.auth_refresh_cookie_name, settings.auth_csrf_cookie_name):
        response.delete_cookie(name)


def create_session(db: Session, user: User, request: Request, restricted: bool = False, family_id: UUID | None = None) -> tuple[AuthSession, str, str, str]:
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.id,
        access_token_hash=token_hash(access_token),
        refresh_token_hash=token_hash(refresh_token),
        csrf_token_hash=token_hash(csrf_token),
        family_id=family_id or uuid4(),
        expires_at=utc_now() + timedelta(days=settings.auth_refresh_days),
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        must_change_password=restricted,
    )
    db.add(session)
    db.flush()
    return session, access_token, refresh_token, csrf_token


def session_from_access_cookie(db: Session, access_token: str | None) -> AuthSession | None:
    if not access_token:
        return None
    access_hash = token_hash(access_token)
    return db.scalar(
        select(AuthSession).where(
            AuthSession.access_token_hash == access_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
    )


def session_from_refresh_cookie(db: Session, refresh_token: str | None) -> AuthSession | None:
    if not refresh_token:
        return None
    return db.scalar(
        select(AuthSession).where(
            AuthSession.refresh_token_hash == token_hash(refresh_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
    )


def revoke_session(db: Session, session: AuthSession, reason: str = "logout") -> None:
    session.revoked_at = utc_now()
    session.revoked_reason = reason
    db.flush()


def revoke_all_sessions(db: Session, user_id: UUID, reason: str = "logout_all") -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now(), revoked_reason=reason)
    )
    db.flush()


def revoke_family(db: Session, family_id: UUID, reason: str = "refresh_reuse") -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now(), revoked_reason=reason)
    )
    db.flush()


def check_user_can_login(user: User) -> None:
    now = utc_now()
    if not user.is_active or not user.authentication_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_FAILURE_DETAIL)
    if user.locked_until and user.locked_until <= now and user.lock_reason == LockReason.TOO_MANY_FAILED_ATTEMPTS:
        user.is_locked = False
        user.locked_until = None
        user.lock_reason = None
        user.failed_login_attempts = 0
    if user.is_locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Учётная запись временно заблокирована. Обратитесь к администратору.")


def record_failed_login(db: Session, user: User | None, request: Request) -> None:
    if user is None:
        return
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.max_failed_login_attempts:
        user.is_locked = True
        user.locked_until = utc_now() + timedelta(minutes=settings.account_lock_minutes)
        user.locked_at = utc_now()
        user.lock_reason = LockReason.TOO_MANY_FAILED_ATTEMPTS
        revoke_all_sessions(db, user.id, "account_locked")
        create_notification(
            db,
            AdminNotificationType.USER_ACCOUNT_LOCKED,
            AdminNotificationSeverity.HIGH,
            "Учётная запись заблокирована",
            f"Пользователь {user.username} временно заблокирован после неуспешных попыток входа.",
            user_id=user.id,
            details={"username": user.username, "ip_address": client_ip(request), "failed_login_attempts": user.failed_login_attempts},
        )
        write_audit(db, "USER_ACCOUNT_LOCKED_AUTOMATICALLY", "User", user.id, new_data={"failed_login_attempts": user.failed_login_attempts})
    db.commit()


def authenticate_local(db: Session, username: str, password: str, request: Request) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_FAILURE_DETAIL)
    check_user_can_login(user)
    if user.auth_source != AuthSource.LOCAL or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_FAILURE_DETAIL)
    if not password_hasher.verify(password, user.password_hash):
        record_failed_login(db, user, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_FAILURE_DETAIL)
    user.failed_login_attempts = 0
    user.last_login_at = utc_now()
    user.last_login_ip = client_ip(request)
    expiry = password_expiry_info(user.password_expires_at)
    if expiry.expired:
        user.must_change_password = True
        user.password_expired_at = user.password_expired_at or utc_now()
        write_audit(db, "PASSWORD_EXPIRED", "User", user.id)
    db.commit()
    db.refresh(user)
    return user


def change_local_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if user.auth_source != AuthSource.LOCAL:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="LOCAL_PASSWORD_NOT_AVAILABLE")
    if not password_hasher.verify(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CURRENT_PASSWORD_INVALID")
    if password_hasher.verify(new_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PASSWORD_REUSE_NOT_ALLOWED")
    validate_password_policy(new_password, user.username)
    user.password_hash = password_hasher.hash(new_password)
    user.password_changed_at = utc_now()
    user.password_expires_at = password_expires_at_from_now()
    user.password_expired_at = None
    user.must_change_password = False
    user.failed_login_attempts = 0
    write_audit(db, "PASSWORD_CHANGED", "User", user.id)
    db.commit()


def set_temporary_password(db: Session, user: User, temporary_password: str, actor_id: UUID | None = None) -> None:
    if user.auth_source != AuthSource.LOCAL:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="LOCAL_PASSWORD_NOT_AVAILABLE")
    validate_password_policy(temporary_password, user.username)
    user.password_hash = password_hasher.hash(temporary_password)
    user.password_changed_at = utc_now()
    user.password_expires_at = password_expires_at_from_now()
    user.must_change_password = True
    user.authentication_enabled = True
    revoke_all_sessions(db, user.id, "temporary_password_generated")
    write_audit(db, "TEMPORARY_PASSWORD_GENERATED", "User", user.id, actor_id=actor_id, new_data={"temporary_password": "***"})
    write_audit(db, "PASSWORD_CHANGE_REQUIRED", "User", user.id, actor_id=actor_id)
    db.flush()
