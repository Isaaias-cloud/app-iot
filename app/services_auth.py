"""Casos de uso de login, refresh, logout y sesión actual."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.config import (
    ACCESS_TOKEN_TTL_SECONDS,
    LOGIN_RATE_LIMIT_MAX,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    REFRESH_TOKEN_TTL_SECONDS,
)
from app.rate_limit import LoginRateLimiter
from app.repositories.auth import AuthRepository
from app.security import AuthContext
from app.tokens import create_token, decode_token, token_hash


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_encoded, digest_encoded = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        import base64
        import hashlib
        salt = base64.urlsafe_b64decode(salt_encoded + "=" * (-len(salt_encoded) % 4))
        expected = base64.urlsafe_b64decode(digest_encoded + "=" * (-len(digest_encoded) % 4))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, int(iterations)
        )
        import hmac
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


class AuthService:
    def __init__(self, repository: AuthRepository | None = None) -> None:
        self.repository = repository or AuthRepository()
        self.rate_limiter = LoginRateLimiter(LOGIN_RATE_LIMIT_MAX, LOGIN_RATE_LIMIT_WINDOW_SECONDS)

    def _audit(self, **kwargs) -> None:
        try:
            self.repository.add_audit(**kwargs)
        except Exception:
            # Un fallo de auditoría no debe convertir un login válido en una
            # respuesta de éxito sin control; el llamador decide el tratamiento.
            raise

    def login(self, email: str, password: str, rate_key: str) -> dict:
        if not self.rate_limiter.allowed(rate_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos de autenticación; inténtalo más tarde.",
            )

        user = self.repository.find_user_by_email(email)
        if user is None or not user["activo"] or not verify_password(password, user["password_hash"]):
            self.rate_limiter.record_failure(rate_key)
            self._audit(
                user_id=None,
                actor_type="SISTEMA",
                action="LOGIN_FAILED",
                resource_type="AUTH",
                resource_id=None,
                detail={"reason": "invalid_credentials"},
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")

        self.rate_limiter.reset(rate_key)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        refresh_exp = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
        # El ID se necesita para firmar el token; se reserva una fila usando un
        # hash aleatorio temporal y se actualiza solo mediante la misma sesión.
        refresh_seed = token_hash(f"refresh-seed:{user['id_usuario']}:{now.isoformat()}")
        refresh_session_id = self.repository.create_session(
            user_id=int(user["id_usuario"]),
            token_type="REFRESH",
            token_hash_value=refresh_seed,
            expires_at=refresh_exp,
        )
        refresh_token = create_token(
            user_id=int(user["id_usuario"]),
            session_id=refresh_session_id,
            token_type="REFRESH",
            ttl_seconds=REFRESH_TOKEN_TTL_SECONDS,
        )
        self.repository.replace_session_token(refresh_session_id, token_hash(refresh_token))
        access_exp = now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        access_seed = token_hash(f"access-seed:{user['id_usuario']}:{now.timestamp()}")
        access_session_id = self.repository.create_session(
            user_id=int(user["id_usuario"]),
            token_type="ACCESS",
            token_hash_value=access_seed,
            expires_at=access_exp,
        )
        access_token = create_token(
            user_id=int(user["id_usuario"]),
            session_id=access_session_id,
            token_type="ACCESS",
            ttl_seconds=ACCESS_TOKEN_TTL_SECONDS,
        )
        self.repository.replace_session_token(access_session_id, token_hash(access_token))
        self._audit(
            user_id=int(user["id_usuario"]),
            actor_type="USUARIO",
            action="LOGIN_SUCCESS",
            resource_type="AUTH",
            resource_id=str(user["id_usuario"]),
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        }

    def refresh(self, refresh_token: str) -> dict:
        claims = decode_token(refresh_token, "REFRESH")
        session = self.repository.get_active_session(int(claims["sid"]), token_hash(refresh_token))
        if session is None or session["tipo"] != "REFRESH":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido.")
        self.repository.revoke_session(int(claims["sid"]), int(claims["sub"]))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        refresh_exp = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
        refresh_seed = token_hash(f"refresh-rotation:{claims['sub']}:{now.timestamp()}")
        refresh_session_id = self.repository.create_session(
            user_id=int(claims["sub"]),
            token_type="REFRESH",
            token_hash_value=refresh_seed,
            expires_at=refresh_exp,
        )
        new_refresh_token = create_token(
            user_id=int(claims["sub"]),
            session_id=refresh_session_id,
            token_type="REFRESH",
            ttl_seconds=REFRESH_TOKEN_TTL_SECONDS,
        )
        self.repository.replace_session_token(refresh_session_id, token_hash(new_refresh_token))
        access_exp = now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        seed = token_hash(f"access-refresh:{claims['sub']}:{now.timestamp()}")
        session_id = self.repository.create_session(
            user_id=int(claims["sub"]), token_type="ACCESS", token_hash_value=seed, expires_at=access_exp
        )
        access_token = create_token(
            user_id=int(claims["sub"]), session_id=session_id,
            token_type="ACCESS", ttl_seconds=ACCESS_TOKEN_TTL_SECONDS
        )
        self.repository.replace_session_token(session_id, token_hash(access_token))
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        }

    def logout(self, context: AuthContext, refresh_token: str | None) -> None:
        if context.session_id is not None and context.user_id is not None:
            self.repository.revoke_session(context.session_id, context.user_id)
            if not refresh_token:
                self.repository.revoke_user_refresh_sessions(context.user_id)
            self._audit(
                user_id=context.user_id,
                actor_type="USUARIO",
                action="LOGOUT",
                resource_type="AUTH",
                resource_id=str(context.user_id),
            )
        if refresh_token:
            self.repository.revoke_token_hash(token_hash(refresh_token))

    def me(self, context: AuthContext) -> dict:
        if context.user_id is None:
            raise HTTPException(status_code=401, detail="Sesión sin usuario.")
        user = self.repository.get_user(context.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Usuario no disponible.")
        return {**user, "roles": sorted(context.roles)}
