"""Endpoints CRUD de comandos IoT."""

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.schemas import (
    ComandoCreate,
    ComandoCreadoResponse,
    ComandoResponse,
    ComandoUpdate,
    OperationResponse,
)
from app.repositories.admin import AdminRepository
from app.services import CommandService
from app.services_movimientos import validate_firmware_code
from app.security import AuthContext, require_admin, require_vehicle_access


router = APIRouter(prefix="/comandos", tags=["Comandos"])
service = CommandService()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


@router.post("/", response_model=ComandoCreadoResponse, status_code=status.HTTP_201_CREATED, summary="Crear comando")
def crear_comando(body: ComandoCreate, _context: AuthContext = Depends(require_admin)):
    try:
        codigo = validate_firmware_code(body.codigo)
        id_comando = service.create(body.id_vehiculo, body.nombre, codigo, body.descripcion)
        commands = service.list_for_vehicle(body.id_vehiculo)
        created = next(
            (command for command in commands if int(command.get("id_comando", -1)) == int(id_comando)),
            None,
        )
        if created is None:
            raise HTTPException(status_code=500, detail="El comando creado no pudo recuperarse")

        repository = AdminRepository()
        unit = repository.get_unit(body.id_vehiculo)
        if unit is not None:
            repository.upsert_model_command(
                int(unit["id_modelo"]),
                id_comando,
                int(created["codigo"]),
                str(created["nombre"]),
                True,
            )
        return {
            "message": "Comando creado",
            "id_comando": id_comando,
            "codigo": int(created["codigo"]),
            "nombre": str(created["nombre"]),
        }
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/vehiculo/{id_vehiculo}", response_model=list[ComandoResponse], summary="Listar comandos del vehículo")
def obtener_comandos_vehiculo(
    id_vehiculo: int = Path(..., gt=0),
    _context: AuthContext = Depends(require_vehicle_access),
):
    try:
        return service.list_for_vehicle(id_vehiculo)
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put("/{id_comando}", response_model=OperationResponse, summary="Actualizar comando")
def actualizar_comando(
    id_comando: int = Path(..., gt=0),
    body: ComandoUpdate = ...,
    _context: AuthContext = Depends(require_admin),
):
    try:
        service.update(
            id_comando,
            body.nombre,
            validate_firmware_code(body.codigo),
            body.descripcion,
            body.activo,
        )
        return {"message": "Operación realizada correctamente", "id": id_comando}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.delete("/{id_comando}", response_model=OperationResponse, summary="Eliminar comando")
def eliminar_comando(
    id_comando: int = Path(..., gt=0),
    _context: AuthContext = Depends(require_admin),
):
    try:
        service.delete(id_comando)
        return {"message": "Comando eliminado correctamente", "id": id_comando}
    except Exception as exc:
        raise _db_error(exc) from exc
