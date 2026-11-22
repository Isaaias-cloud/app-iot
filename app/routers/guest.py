"""Catálogo público y sesiones exclusivas de exhibición."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.routers.hardware_ws import stop_vehicle_safely
from app.schemas import GuestSessionCreate, GuestSessionResponse, GuestVehicleResponse, OperationResponse
from app.security import AuthContext, get_auth_context
from app.services_guest import GuestService


router = APIRouter(prefix="/invitado", tags=["Modo invitado"])
service = GuestService()


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
    result = service.finalize(context.guest_session_id)
    await stop_vehicle_safely(int(result["id"]))
    return result
