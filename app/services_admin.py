"""Servicios de la administración y del contexto de usuario."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from app.repositories.admin import AdminRepository
from app.repositories.auth import AccessRepository, AuthRepository


def hash_password(password: str) -> str:
    """Genera un hash PBKDF2 portable; nunca se persiste la contraseña plana."""
    iterations = 600_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return f"pbkdf2_sha256${iterations}${encode(salt)}${encode(digest)}"


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


class AdminService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def dashboard(self) -> dict[str, int]:
        return self.repository.dashboard()

    def list_models(self, limit: int, offset: int, search: str | None) -> list[dict[str, Any]]:
        return self.repository.list_models(limit, offset, search)

    def create_model(self, values: dict[str, Any]) -> dict[str, Any]:
        model_id = self.repository.create_model(values)
        result = self.repository.get_model(model_id)
        if result is None:
            raise _not_found("El modelo no pudo recuperarse después de crearlo.")
        return result

    def update_model(self, model_id: int, values: dict[str, Any]) -> dict[str, Any]:
        if self.repository.update_model(model_id, values) == 0:
            raise _not_found("Modelo no encontrado.")
        result = self.repository.get_model(model_id)
        if result is None:
            raise _not_found("Modelo no encontrado.")
        return result

    def update_model_command(self, model_id: int, command_id: int, permitido: bool) -> dict[str, Any]:
        if self.repository.update_model_command(model_id, command_id, permitido) == 0:
            raise _not_found("La capacidad de comando no existe para este modelo.")
        result = self.repository.get_model_command(model_id, command_id)
        if result is None:
            raise _not_found("La capacidad de comando no existe para este modelo.")
        return result

    def list_model_commands(self, model_id: int) -> list[dict[str, Any]]:
        return self.repository.list_model_commands(model_id)

    def list_units(self, limit: int, offset: int, inventory_state: str | None) -> list[dict[str, Any]]:
        return self.repository.list_units(limit, offset, inventory_state)

    def create_unit(self, values: dict[str, Any]) -> dict[str, Any]:
        vehicle_id = self.repository.create_unit(values)
        if vehicle_id == 0:
            raise _not_found("Modelo no encontrado.")
        result = self.repository.get_unit(vehicle_id)
        if result is None:
            raise _not_found("La unidad no pudo recuperarse después de crearla.")
        return result

    def update_unit(self, vehicle_id: int, values: dict[str, Any]) -> dict[str, Any]:
        if self.repository.update_unit(vehicle_id, values) == 0:
            raise _not_found("Unidad no encontrada.")
        result = self.repository.get_unit(vehicle_id)
        if result is None:
            raise _not_found("Unidad no encontrada.")
        return result

    def list_clients(self, limit: int, offset: int, search: str | None) -> list[dict[str, Any]]:
        return self.repository.list_clients(limit, offset, search)

    def create_client(self, values: dict[str, Any]) -> dict[str, Any]:
        payload = {
            **values,
            "password_hash": hash_password(values["password"]),
        }
        payload.pop("password", None)
        user_id = self.repository.create_client(payload)
        if user_id == 0:
            raise _not_found("El rol USUARIO no está configurado.")
        return self.repository.get_client(user_id) or {"id_usuario": user_id}

    def update_client(self, user_id: int, values: dict[str, Any]) -> dict[str, Any]:
        if self.repository.update_client(user_id, values) == 0:
            raise _not_found("Cliente no encontrado.")
        return self.repository.get_client(user_id) or {"id_usuario": user_id}

    def list_assignments(self, limit: int, offset: int, vehicle_id: int | None) -> list[dict[str, Any]]:
        return self.repository.list_assignments(limit, offset, vehicle_id)

    def create_assignment(self, values: dict[str, Any], admin_id: int) -> dict[str, Any]:
        assignment_id = self.repository.create_assignment({**values, "creado_por": admin_id})
        return self.repository.get_assignment(assignment_id) or {"id_asignacion": assignment_id}

    def revoke_assignment(self, assignment_id: int, reason: str | None) -> dict[str, Any]:
        if self.repository.revoke_assignment(assignment_id, reason) == 0:
            raise _not_found("Asignación activa no encontrada.")
        return {"message": "Asignación revocada", "id": assignment_id}

    def list_audit(self, limit: int, offset: int, resource_type: str | None) -> list[dict[str, Any]]:
        return self.repository.list_audit(limit, offset, resource_type)

    def list_my_vehicles(self, user_id: int, limit: int, offset: int, include_support: bool = False) -> list[dict[str, Any]]:
        return self.repository.list_my_vehicles(user_id, limit, offset, include_support)

    def list_admins(self) -> list[dict[str, Any]]:
        return self.repository.list_admins()


class SupportService:
    def __init__(self, repository: AccessRepository | None = None) -> None:
        self.repository = repository or AccessRepository()
        self.audit = AuthRepository()

    def list_for_owner(self, vehicle_id: int, owner_id: int) -> list[dict[str, Any]]:
        return self.repository.list_support_authorizations(vehicle_id, owner_id)

    def create_for_owner(
        self,
        vehicle_id: int,
        owner_id: int,
        admin_id: int,
        reason: str,
    ) -> dict[str, Any]:
        resource = self.repository.vehicle_access(vehicle_id, owner_id, "USUARIO", None)
        if resource is None or not bool(resource["es_propietario"]):
            raise HTTPException(status_code=403, detail="Solo el propietario activo puede otorgar soporte.")
        if not self.repository.is_admin(admin_id):
            raise _not_found("El usuario destino no tiene rol ADMIN.")
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
        authorization_id = self.repository.create_support_authorization(
            vehicle_id=vehicle_id,
            owner_id=owner_id,
            admin_id=admin_id,
            reason=reason,
            expires_at=expires_at,
        )
        self.audit.add_audit(
            user_id=owner_id,
            actor_type="USUARIO",
            action="SUPPORT_AUTHORIZATION_GRANTED",
            resource_type="VEHICULO",
            resource_id=str(vehicle_id),
            detail={"authorization_id": authorization_id, "admin_id": admin_id},
        )
        return self.repository.get_support_authorization(authorization_id) or {
            "id_autorizacion": authorization_id
        }

    def revoke_for_owner(self, authorization_id: int, owner_id: int) -> dict[str, Any]:
        if self.repository.revoke_support_authorization(authorization_id, owner_id) == 0:
            raise _not_found("Autorización activa no encontrada.")
        self.audit.add_audit(
            user_id=owner_id,
            actor_type="USUARIO",
            action="SUPPORT_AUTHORIZATION_REVOKED",
            resource_type="AUTORIZACION_SOPORTE",
            resource_id=str(authorization_id),
        )
        return {"message": "Autorización de soporte revocada", "id": authorization_id}
