"""Autenticación, RBAC y autorización por recurso."""

from dataclasses import dataclass
import hmac
from typing import FrozenSet

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories.auth import AccessRepository, AuthRepository
from app.config import DEVICE_TOKENS
from app.tokens import decode_token, token_hash


bearer_scheme = HTTPBearer(auto_error=False)
auth_repository = AuthRepository()
access_repository = AccessRepository()


@dataclass(frozen=True)
class AuthContext:
    user_id: int | None
    roles: FrozenSet[str]
    session_id: int | None = None
    guest_session_id: int | None = None
    token_hash: str | None = None
    device_vehicle_id: int | None = None


def authenticate_raw_token(raw_token: str) -> AuthContext:
    """Valida firma, expiración y revocación en RDS."""
    try:
        claims = decode_token(raw_token, "ACCESS")
        user_id = int(claims["sub"])
        session_id = int(claims["sid"])
        hashed = token_hash(raw_token)
        if claims.get("rol") == "INVITADO":
            guest = access_repository.guest_context(hashed)
            if guest is None or int(guest["id_sesion_invitado"]) != session_id:
                raise HTTPException(status_code=401, detail="Sesión de invitado inválida o expirada.")
            if int(claims.get("id_vehiculo", 0)) != int(guest["id_vehiculo"]):
                raise HTTPException(status_code=403, detail="El token de invitado no coincide con su reserva.")
            return AuthContext(
                user_id=None,
                roles=frozenset({"INVITADO"}),
                guest_session_id=session_id,
                token_hash=hashed,
            )
        session = auth_repository.get_active_session(session_id, hashed)
        if session is None or session["tipo"] != "ACCESS" or int(session["id_usuario"]) != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión inválida, expirada o revocada.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        roles = auth_repository.get_roles(user_id)
        auth_repository.touch_session(session_id)
        return AuthContext(user_id=user_id, roles=roles, session_id=session_id, token_hash=hashed)
    except HTTPException as token_error:
        # Invitados usan el token opaco de sesiones_invitado; no se les asigna
        # un usuario persistente ni se confía en un rol enviado por el cliente.
        if token_error.status_code == status.HTTP_401_UNAUTHORIZED:
            guest = access_repository.guest_context(token_hash(raw_token))
            if guest is not None:
                return AuthContext(
                    user_id=None,
                    roles=frozenset({"INVITADO"}),
                    guest_session_id=int(guest["id_sesion_invitado"]),
                    token_hash=token_hash(raw_token),
                )
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def authenticate_http(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authenticate_raw_token(credentials.credentials)


def get_auth_context(context: AuthContext = Depends(authenticate_http)) -> AuthContext:
    return context


def require_admin(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if "ADMIN" not in context.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere el rol ADMIN.")
    return context


def require_user_or_admin(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not {"ADMIN", "USUARIO"}.intersection(context.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes.")
    return context


def require_non_guest(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if "INVITADO" in context.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El modo invitado no puede modificar este recurso.")
    return context


def authorize_vehicle(context: AuthContext, vehicle_id: int) -> dict:
    if context.user_id is None and "INVITADO" not in context.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sesión sin usuario.")
    resource = access_repository.vehicle_access(
        vehicle_id,
        context.user_id or 0,
        next(iter(context.roles), ""),
        context.guest_session_id,
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad no encontrada.")

    inventory_state = resource["estado_inventario"]
    if "ADMIN" in context.roles:
        if inventory_state == "VENDIDA" and not bool(resource["tiene_soporte"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El administrador necesita autorización de soporte vigente para esta unidad vendida.",
            )
        return resource

    if "USUARIO" in context.roles and bool(resource["es_propietario"]):
        return resource

    if "INVITADO" in context.roles and bool(resource["tiene_reserva"]):
        return resource

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta unidad.")


def require_vehicle_access(
    id_vehiculo: int = Path(..., gt=0),
    context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    authorize_vehicle(context, id_vehiculo)
    return context


def require_demo_access(
    id_demo: int = Path(..., gt=0),
    context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    vehicle_id = access_repository.demo_vehicle(id_demo)
    if vehicle_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo no encontrada.")
    scope = access_repository.demo_scope(id_demo)
    if "INVITADO" in context.roles and (scope is None or scope.get("alcance") != "EMPRESA"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El modo invitado solo puede usar demos de empresa.")
    authorize_vehicle(context, vehicle_id)
    return context


def require_allowed_command(vehicle_id: int, command_id: int) -> dict:
    command = access_repository.allowed_command(vehicle_id, command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El comando no está permitido para el modelo de la unidad.",
        )
    return command


def authenticate_websocket_token(raw_token: str) -> AuthContext:
    """Variante para handshake WSS; el token se valida antes de ``accept``."""
    return authenticate_raw_token(raw_token)


def authenticate_device_token(raw_token: str, vehicle_id: int) -> AuthContext:
    """Valida un secreto permanente de hardware para su única unidad asignada."""
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de dispositivo requerido.")

    assigned_vehicle_id = None
    for configured_vehicle_id, configured_token in DEVICE_TOKENS.items():
        if hmac.compare_digest(configured_token, raw_token):
            assigned_vehicle_id = configured_vehicle_id
            break
    if assigned_vehicle_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de dispositivo inválido.")
    if assigned_vehicle_id != vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token de dispositivo no corresponde a esta unidad.",
        )
    return AuthContext(
        user_id=None,
        roles=frozenset({"DISPOSITIVO"}),
        device_vehicle_id=assigned_vehicle_id,
    )


def is_device_context(context: AuthContext) -> bool:
    return "DISPOSITIVO" in context.roles and context.device_vehicle_id is not None
