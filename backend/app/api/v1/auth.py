from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user_stub, require_csrf
from app.core.config import settings
from app.db.session import get_db
from app.models.admin import AuthSource, User
from app.schemas.auth import AuthMeResponse, ChangePasswordRequest, LoginRequest, LoginResponse, MessageResponse, ProviderStatus
from app.services.auth_service import (
    authenticate_local,
    change_local_password,
    clear_auth_cookies,
    create_session,
    revoke_all_sessions,
    revoke_family,
    revoke_session,
    session_from_refresh_cookie,
    set_auth_cookies,
)
from app.services.password_service import password_expiry_info
from app.services.rbac_service import permission_codes_for_user

router = APIRouter(prefix="/auth", tags=["auth"])


def serialize_auth_user(user: User) -> AuthMeResponse:
    expiry = password_expiry_info(user.password_expires_at) if user.auth_source == AuthSource.LOCAL else password_expiry_info(None)
    return AuthMeResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        user_type=user.user_type.value,
        auth_source=user.auth_source.value,
        is_active=user.is_active,
        is_locked=user.is_locked,
        must_change_password=user.must_change_password,
        password_expires_at=user.password_expires_at,
        password_expired=expiry.expired,
        password_days_remaining=expiry.days_remaining,
        password_expiry_warning=expiry.warning,
        role_ids=[item.role_id for item in user.roles],
        role_codes=[item.role.code for item in user.roles if item.role],
        permissions=sorted(permission_codes_for_user(user)),
        contractor_memberships=user.contractor_memberships,
    )


@router.get("/providers", response_model=list[ProviderStatus])
def providers() -> list[ProviderStatus]:
    return [
        ProviderStatus(provider="LOCAL", configured=True, enabled=True),
        ProviderStatus(provider="LDAP", configured=False, enabled=False, message="LDAP не настроен"),
        ProviderStatus(provider="ADFS", configured=False, enabled=False, message="ADFS не настроен"),
    ]


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    if payload.provider != "LOCAL":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PROVIDER_NOT_CONFIGURED")
    user = authenticate_local(db, payload.username, payload.password, request)
    restricted = user.must_change_password
    session, access_token, refresh_token, csrf_token = create_session(db, user, request, restricted=restricted)
    db.commit()
    set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return LoginResponse(user=serialize_auth_user(user), must_change_password=restricted)


@router.get("/me", response_model=AuthMeResponse)
def me(user: User = Depends(get_current_user_stub)) -> AuthMeResponse:
    return serialize_auth_user(user)


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.auth_refresh_cookie_name),
    db: Session = Depends(get_db),
) -> LoginResponse:
    old_session = session_from_refresh_cookie(db, refresh_cookie)
    if old_session is None:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    user = old_session.user
    revoke_session(db, old_session, "refresh_rotation")
    session, access_token, refresh_token, csrf_token = create_session(db, user, request, restricted=old_session.must_change_password, family_id=old_session.family_id)
    db.commit()
    set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return LoginResponse(user=serialize_auth_user(user), must_change_password=session.must_change_password)


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response, session=Depends(get_current_session), db: Session = Depends(get_db)) -> MessageResponse:
    revoke_session(db, session, "logout")
    db.commit()
    clear_auth_cookies(response)
    return MessageResponse(message="ok")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(response: Response, user: User = Depends(get_current_user_stub), db: Session = Depends(get_db)) -> MessageResponse:
    revoke_all_sessions(db, user.id, "logout_all")
    db.commit()
    clear_auth_cookies(response)
    return MessageResponse(message="ok")


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, session=Depends(get_current_session), db: Session = Depends(get_db)) -> MessageResponse:
    user = session.user
    change_local_password(db, user, payload.current_password, payload.new_password)
    session.must_change_password = False
    db.commit()
    return MessageResponse(message="ok")


@router.get("/adfs/login")
def adfs_login() -> MessageResponse:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PROVIDER_NOT_CONFIGURED")


@router.get("/adfs/callback")
def adfs_callback() -> MessageResponse:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PROVIDER_NOT_CONFIGURED")
