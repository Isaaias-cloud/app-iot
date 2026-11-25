"""Catálogo público y sesiones exclusivas de exhibición."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.routers.hardware_ws import stop_vehicle_safely
from app.schemas import GuestSessionCreate, GuestSessionResponse, GuestVehicleResponse, OperationResponse
from app.security import AuthContext, get_auth_context
from app.services_guest import GuestService


router = APIRouter(prefix="/invitado", tags=["Modo invitado"])
service = GuestService()
logger = logging.getLogger(__name__)


@router.get("/vehiculos", response_model=list[GuestVehicleResponse])
def catalogo_exhibicion():
    return service.catalog()


@router.post("/sesion", response_model=GuestSessionResponse, status_code=status.HTTP_201_CREATED)
def iniciar_sesion_invitado(body: GuestSessionCreate, request: Request):
    client = request.client.host if request.client else "unknown"
    return service.reserve(body.id_vehiculo, client)


@router.post("/sesion/finalizar", response_model=OperationResponse)
async def finalizar_sesion_invitado(context: AuthContext = Depends(get_auth_context)):
    if "INVITADO" not in context.roles or context.guest_session_id is None:
        raise HTTPException(status_code=403, detail="La ruta solo está disponible para sesiones de invitado.")
    session = service.repository.guest_session_by_id(context.guest_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión de invitado no encontrada.")
    id_vehiculo = int(session["id_vehiculo"])

    result = None
    try:
        result = service.finalize(context.guest_session_id)
    except Exception:
        logger.exception("No se pudo finalizar la sesión de invitado id_sesion=%s", context.guest_session_id)

    await stop_vehicle_safely(id_vehiculo)
    return result or {"message": "Sesión de exhibición finalizada con incidencia", "id": id_vehiculo}
