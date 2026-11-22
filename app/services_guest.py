"""Casos de uso de modo invitado y reservas de exhibición."""

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.rate_limit import LoginRateLimiter
from app.repositories.auth import AuthRepository
from app.repositories.guest import GuestRepository
from app.tokens import create_guest_token, token_hash


class GuestService:
    def __init__(self, repository: GuestRepository | None = None, audit: AuthRepository | None = None) -> None:
        self.repository = repository or GuestRepository()
        self.audit = audit or AuthRepository()
        self.rate_limiter = LoginRateLimiter(3, 60)

    def catalog(self) -> list[dict]:
        return self.repository.exhibition_catalog()

    def reserve(self, vehicle_id: int, rate_key: str) -> dict:
        if not self.rate_limiter.allowed(rate_key):
            raise HTTPException(status_code=429, detail="Demasiadas reservas de invitado; inténtalo más tarde.")
        seed = token_hash(f"guest:{vehicle_id}:{rate_key}:{secrets.token_urlsafe(24)}")
        result = self.repository.reserve(vehicle_id, seed)
        if result is None:
            self.rate_limiter.record_failure(rate_key)
            raise HTTPException(status_code=409, detail="La unidad no está disponible para exhibición.")
        if result.get("conflict"):
            self.rate_limiter.record_failure(rate_key)
            raise HTTPException(status_code=409, detail="La unidad ya tiene una reserva activa.")
        session_id = int(result["id_sesion_invitado"])
        token = create_guest_token(session_id=session_id, vehicle_id=vehicle_id, ttl_seconds=300)
        self.repository.replace_token_hash(session_id, token_hash(token))
        self.rate_limiter.reset(rate_key)
        self.audit.add_audit(
            user_id=None,
            actor_type="INVITADO",
            action="GUEST_RESERVATION_CREATED",
            resource_type="VEHICULO",
            resource_id=str(vehicle_id),
            detail={"id_sesion_invitado": session_id, "expira_en": str(result["expira_en"])},
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 300,
            "id_vehiculo": vehicle_id,
            "id_sesion_invitado": session_id,
            "expira_en": result["expira_en"],
        }

    def finalize(self, session_id: int) -> dict:
        session = self.repository.release_guest_session(session_id, "CANCELADA")
        if session is None:
            raise HTTPException(status_code=404, detail="Sesión de invitado no encontrada.")
        self.audit.add_audit(
            user_id=None,
            actor_type="INVITADO",
            action="GUEST_RESERVATION_CANCELLED",
            resource_type="VEHICULO",
            resource_id=str(session["id_vehiculo"]),
            detail={"id_sesion_invitado": session_id},
        )
        return {"message": "Sesión de exhibición finalizada", "id": session["id_vehiculo"]}

    def release_connection(self, session_id: int, expired: bool = False) -> dict | None:
        result = self.repository.release_guest_session(session_id, "EXPIRADA" if expired else "DESCONECTADA")
        if result and result.get("estado") == "ACTIVA":
            self.audit.add_audit(
                user_id=None,
                actor_type="INVITADO",
                action="GUEST_RESERVATION_EXPIRED" if expired else "GUEST_RESERVATION_DISCONNECTED",
                resource_type="VEHICULO",
                resource_id=str(result["id_vehiculo"]),
                detail={"id_sesion_invitado": session_id},
            )
        return result
