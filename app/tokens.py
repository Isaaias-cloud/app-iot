"""Tokens HS256 mínimos, sin secretos embebidos ni dependencia adicional."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, status

from app.config import JWT_ISSUER, JWT_SECRET


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _secret() -> bytes:
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La firma de tokens no está configurada de forma segura.",
        )
    return JWT_SECRET.encode("utf-8")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(*, user_id: int, session_id: int, token_type: str, ttl_seconds: int, role: str | None = None, vehicle_id: int | None = None) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": JWT_ISSUER,
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": token_type,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_urlsafe(16),
    }
    if role:
        payload["rol"] = role
    if vehicle_id is not None:
        payload["id_vehiculo"] = int(vehicle_id)
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    unsigned = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(_secret(), unsigned, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64encode(signature)}"


def create_guest_token(*, session_id: int, vehicle_id: int, ttl_seconds: int = 300) -> str:
    return create_token(
        user_id=0,
        session_id=session_id,
        token_type="ACCESS",
        ttl_seconds=ttl_seconds,
        role="INVITADO",
        vehicle_id=vehicle_id,
    )


def decode_token(token: str, expected_type: str = "ACCESS") -> dict[str, Any]:
    try:
        header, encoded_payload, encoded_signature = token.split(".")
        unsigned = f"{header}.{encoded_payload}".encode("ascii")
        expected_signature = hmac.new(_secret(), unsigned, hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(encoded_signature), expected_signature):
            raise ValueError("signature")
        payload = json.loads(_b64decode(encoded_payload))
        if payload.get("iss") != JWT_ISSUER or payload.get("typ") != expected_type:
            raise ValueError("claims")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired")
        if not str(payload.get("sub", "")).isdigit() or not str(payload.get("sid", "")).isdigit():
            raise ValueError("subject")
        return payload
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
