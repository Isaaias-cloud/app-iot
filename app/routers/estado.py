"""Endpoints del estado actual de cada vehículo."""

from fastapi import APIRouter, HTTPException, Path

from app.schemas import EstadoResponse, EstadoUpdate, OperationResponse
from app.services import StateService


router = APIRouter(prefix="/estado", tags=["Estado"])
service = StateService()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


@router.put("/vehiculo/{id_vehiculo}", response_model=OperationResponse, summary="Actualizar estado del vehículo")
def actualizar_estado(id_vehiculo: int = Path(..., gt=0), body: EstadoUpdate = ...):
    try:
        service.update(id_vehiculo, body.id_comando, body.conectado)
        return {"message": "Operación realizada correctamente", "id": id_vehiculo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/vehiculo/{id_vehiculo}", response_model=EstadoResponse, summary="Obtener estado del vehículo")
def obtener_estado(id_vehiculo: int = Path(..., gt=0)):
    try:
        rows = service.get(id_vehiculo)
        return rows[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise _db_error(exc) from exc
