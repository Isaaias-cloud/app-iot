"""Endpoints del estado actual de cada vehículo."""

from fastapi import APIRouter, Depends, HTTPException, Path

from app.schemas import EstadoResponse, EstadoUpdate, OperationResponse
from app.services import StateService
from app.repositories.auth import AccessRepository
from app.security import AuthContext, require_allowed_command, require_vehicle_access


router = APIRouter(prefix="/estado", tags=["Estado"])
service = StateService()
access_repository = AccessRepository()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


@router.put("/vehiculo/{id_vehiculo}", response_model=OperationResponse, summary="Actualizar estado del vehículo")
def actualizar_estado(
    id_vehiculo: int = Path(..., gt=0),
    body: EstadoUpdate = ...,
    _context: AuthContext = Depends(require_vehicle_access),
):
    try:
        require_allowed_command(id_vehiculo, body.id_comando)
        service.update(id_vehiculo, body.id_comando, body.conectado)
        return {"message": "Operación realizada correctamente", "id": id_vehiculo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/vehiculo/{id_vehiculo}", response_model=EstadoResponse, summary="Obtener estado del vehículo")
def obtener_estado(
    id_vehiculo: int = Path(..., gt=0),
    _context: AuthContext = Depends(require_vehicle_access),
):
    try:
        rows = service.get(id_vehiculo)
        return rows[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise _db_error(exc) from exc
