import base64
import hashlib
import hmac
import json
import secrets

from fastapi import HTTPException, status

from app.core.config import settings


def require_key() -> bytes:
    key = settings.connection_secrets_key
    if not key:
        if settings.environment.lower() in {"production", "prod"}:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="CONNECTION_SECRETS_KEY_REQUIRED")
        key = "development-only-connection-secret-key"
    return hashlib.sha256(key.encode("utf-8")).digest()


def xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < len(data):
        output.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(a ^ b for a, b in zip(data, output))


def encrypt_json(value: dict | None) -> dict | None:
    if not value:
        return None
    key = require_key()
    nonce = secrets.token_bytes(16)
    plaintext = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ciphertext = xor_stream(plaintext, key, nonce)
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return {
        "alg": "SP-HMAC-XOR-DEV",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }


def decrypt_json(envelope: dict | None) -> dict:
    if not envelope:
        return {}
    key = require_key()
    nonce = base64.b64decode(envelope["nonce"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, base64.b64decode(envelope["tag"])):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="SECRET_AUTHENTICATION_FAILED")
    return json.loads(xor_stream(ciphertext, key, nonce).decode("utf-8"))


def mask_secrets(data: dict | None) -> dict:
    return {key: "***" for key in (data or {})}
