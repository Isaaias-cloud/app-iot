"""Endpoints CRUD de comandos IoT."""

from fastapi import APIRouter, HTTPException, Path, status

from app.schemas import (
    ComandoCreate,
    ComandoCreadoResponse,
    ComandoResponse,
    ComandoUpdate,
    OperationResponse,
)
from app.services import CommandService


router = APIRouter(prefix="/comandos", tags=["Comandos"])
service = CommandService()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


@router.post("/", response_model=ComandoCreadoResponse, status_code=status.HTTP_201_CREATED, summary="Crear comando")
def crear_comando(body: ComandoCreate):
    try:
        id_comando = service.create(body.id_vehiculo, body.nombre, body.codigo, body.descripcion)
        return {"message": "Comando creado", "id_comando": id_comando}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/vehiculo/{id_vehiculo}", response_model=list[ComandoResponse], summary="Listar comandos del vehículo")
def obtener_comandos_vehiculo(id_vehiculo: int = Path(..., gt=0)):
    try:
        return service.list_for_vehicle(id_vehiculo)
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put("/{id_comando}", response_model=OperationResponse, summary="Actualizar comando")
def actualizar_comando(id_comando: int = Path(..., gt=0), body: ComandoUpdate = ...):
    try:
        service.update(
            id_comando,
            body.nombre,
            body.codigo,
            body.descripcion,
            body.activo,
        )
        return {"message": "Operación realizada correctamente", "id": id_comando}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.delete("/{id_comando}", response_model=OperationResponse, summary="Eliminar comando")
def eliminar_comando(id_comando: int = Path(..., gt=0)):
    try:
        service.delete(id_comando)
        return {"message": "Comando eliminado correctamente", "id": id_comando}
    except Exception as exc:
        raise _db_error(exc) from exc
