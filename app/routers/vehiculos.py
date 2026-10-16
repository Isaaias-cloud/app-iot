"""Endpoints CRUD de vehículos."""

from fastapi import APIRouter, HTTPException, Path, status

from app.schemas import OperationResponse, VehiculoCreate, VehiculoResponse, VehiculoUpdate
from app.services import VehicleService


router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])
service = VehicleService()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


@router.post("/", response_model=VehiculoResponse, status_code=status.HTTP_201_CREATED, summary="Crear vehículo")
def crear_vehiculo(body: VehiculoCreate):
    try:
        rows = service.create(
            body.nombre,
            body.modelo,
            body.descripcion,
            body.microcontrolador,
        )
        return rows[0] if rows else body.model_dump()
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/", response_model=list[VehiculoResponse], summary="Listar vehículos")
def obtener_vehiculos():
    try:
        return service.list()
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/{id_vehiculo}", response_model=VehiculoResponse, summary="Obtener vehículo")
def obtener_vehiculo(id_vehiculo: int = Path(..., gt=0)):
    try:
        rows = service.get(id_vehiculo)
        if not rows:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")
        return rows[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put("/{id_vehiculo}", response_model=OperationResponse, summary="Actualizar vehículo")
def actualizar_vehiculo(id_vehiculo: int = Path(..., gt=0), body: VehiculoUpdate = ...):
    try:
        service.update(
            id_vehiculo,
            body.nombre,
            body.modelo,
            body.descripcion,
            body.microcontrolador,
            body.activo,
        )
        return {"message": "Operación realizada correctamente", "id": id_vehiculo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.delete("/{id_vehiculo}", response_model=OperationResponse, summary="Eliminar vehículo")
def eliminar_vehiculo(id_vehiculo: int = Path(..., gt=0)):
    try:
        service.delete(id_vehiculo)
        return {"message": "Vehículo eliminado correctamente", "id": id_vehiculo}
    except Exception as exc:
        raise _db_error(exc) from exc
