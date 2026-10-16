"""CRUD de demos y de sus movimientos programados."""

from fastapi import APIRouter, HTTPException, Path, status

from app.schemas import (
    DemoCreate,
    DemoMovimientoCreate,
    DemoMovimientoResponse,
    DemoMovimientoUpdate,
    DemoResponse,
    DemoUpdate,
    OperationResponse,
)
from app.services import DemoService


router = APIRouter(prefix="/demos", tags=["Demos"])
service = DemoService()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


@router.post("/", response_model=DemoResponse, status_code=status.HTTP_201_CREATED, summary="Crear demo")
def crear_demo(body: DemoCreate):
    try:
        rows = service.create(body.id_vehiculo, body.nombre, body.descripcion)
        return rows[0] if rows else body.model_dump()
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/vehiculo/{id_vehiculo}", response_model=list[DemoResponse], summary="Listar demos del vehículo")
def obtener_demos(id_vehiculo: int = Path(..., gt=0)):
    try:
        return service.list_for_vehicle(id_vehiculo)
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put("/{id_demo}", response_model=OperationResponse, summary="Actualizar demo")
def actualizar_demo(id_demo: int = Path(..., gt=0), body: DemoUpdate = ...):
    try:
        service.update(id_demo, body.nombre, body.descripcion, body.activo)
        return {"message": "Operación realizada correctamente", "id": id_demo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.delete("/{id_demo}", response_model=OperationResponse, summary="Eliminar demo")
def eliminar_demo(id_demo: int = Path(..., gt=0)):
    try:
        service.delete(id_demo)
        return {"message": "Demo eliminada correctamente", "id": id_demo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.post(
    "/movimiento",
    response_model=DemoMovimientoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar movimiento a una demo",
)
def agregar_movimiento_demo(body: DemoMovimientoCreate):
    try:
        rows = service.add_movement(
            body.id_demo,
            body.id_comando,
            body.orden,
            body.duracion_ms,
            body.pausa_ms,
        )
        return rows[0] if rows else body.model_dump()
    except Exception as exc:
        raise _db_error(exc) from exc


# Compatibilidad con el plural de la primera versión; la ruta documentada es
# /demos/movimiento, que coincide con la firma actual de la práctica.
router.add_api_route(
    "/movimientos",
    agregar_movimiento_demo,
    methods=["POST"],
    include_in_schema=False,
)


@router.get("/{id_demo}/movimientos", response_model=list[DemoMovimientoResponse], summary="Listar movimientos de una demo")
def obtener_movimientos_demo(id_demo: int = Path(..., gt=0)):
    try:
        return service.list_movements(id_demo)
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put(
    "/movimiento/{id_demo_movimiento}",
    response_model=OperationResponse,
    summary="Actualizar movimiento de demo",
)
def actualizar_movimiento_demo(
    id_demo_movimiento: int = Path(..., gt=0),
    body: DemoMovimientoUpdate = ...,
):
    try:
        service.update_movement(
            id_demo_movimiento,
            body.id_comando,
            body.orden,
            body.duracion_ms,
            body.pausa_ms,
        )
        return {
            "message": "Operación realizada correctamente",
            "id": id_demo_movimiento,
        }
    except Exception as exc:
        raise _db_error(exc) from exc


router.add_api_route(
    "/movimientos/{id_demo_movimiento}",
    actualizar_movimiento_demo,
    methods=["PUT"],
    include_in_schema=False,
)


@router.delete(
    "/movimientos/{id_demo_movimiento}",
    response_model=OperationResponse,
    summary="Eliminar movimiento de demo",
)
def eliminar_movimiento_demo(id_demo_movimiento: int = Path(..., gt=0)):
    try:
        service.delete_movement(id_demo_movimiento)
        return {
            "message": "Movimiento de demo eliminado correctamente",
            "id": id_demo_movimiento,
        }
    except Exception as exc:
        raise _db_error(exc) from exc


router.add_api_route(
    "/movimiento/{id_demo_movimiento}",
    eliminar_movimiento_demo,
    methods=["DELETE"],
    response_model=OperationResponse,
    include_in_schema=False,
)
