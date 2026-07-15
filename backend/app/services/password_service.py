import base64
import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.reference_data import utc_now


@dataclass(frozen=True)
class PasswordExpiryInfo:
    expired: bool
    days_remaining: int | None
    warning: bool


class PasswordHasher:
    def hash(self, password: str) -> str:
        try:
            from argon2 import PasswordHasher as Argon2PasswordHasher  # type: ignore

            return "argon2$" + Argon2PasswordHasher().hash(password)
        except Exception:
            salt = secrets.token_bytes(16)
            iterations = 390_000
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return "pbkdf2_sha256$%d$%s$%s" % (
                iterations,
                base64.b64encode(salt).decode("ascii"),
                base64.b64encode(digest).decode("ascii"),
            )

    def verify(self, password: str, password_hash: str | None) -> bool:
        if not password_hash:
            return False
        if password_hash.startswith("argon2$"):
            try:
                from argon2 import PasswordHasher as Argon2PasswordHasher  # type: ignore

                return Argon2PasswordHasher().verify(password_hash.removeprefix("argon2$"), password)
            except Exception:
                return False
        if password_hash.startswith("pbkdf2_sha256$"):
            try:
                _, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
                digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_raw), int(iterations_raw))
                return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), digest_raw)
            except Exception:
                return False
        return False


password_hasher = PasswordHasher()


def validate_password_policy(password: str, username: str | None = None) -> None:
    if not password or not password.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_EMPTY")
    if len(password) < settings.password_min_length:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_TOO_SHORT")
    if len(password) > settings.password_max_length:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_TOO_LONG")
    if username and password.lower() == username.lower():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_EQUALS_USERNAME")
    if settings.password_require_uppercase and not any(ch.isupper() for ch in password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_REQUIRES_UPPERCASE")
    if settings.password_require_lowercase and not any(ch.islower() for ch in password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_REQUIRES_LOWERCASE")
    if settings.password_require_digit and not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_REQUIRES_DIGIT")
    if settings.password_require_special and not any(ch in string.punctuation for ch in password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PASSWORD_REQUIRES_SPECIAL")


def generate_temporary_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            validate_password_policy(password)
            return password
        except HTTPException:
            continue


def password_expires_at_from_now():
    return utc_now() + timedelta(days=settings.password_max_age_days)


def password_expiry_info(password_expires_at) -> PasswordExpiryInfo:
    if password_expires_at is None:
        return PasswordExpiryInfo(expired=False, days_remaining=None, warning=False)
    now = utc_now()
    if password_expires_at.tzinfo is None:
        password_expires_at = password_expires_at.replace(tzinfo=now.tzinfo)
    remaining = password_expires_at - now
    days = max(0, remaining.days)
    expired = remaining.total_seconds() <= 0
    return PasswordExpiryInfo(expired=expired, days_remaining=days, warning=not expired and days <= settings.password_expiry_warning_days)
