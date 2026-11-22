"""CRUD de demos y de sus movimientos programados."""

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.schemas import (
    DemoCreate,
    DemoCreateResponse,
    DemoMovimientoCreate,
    DemoMovimientoCreateResponse,
    DemoMovimientoResponse,
    DemoMovimientoUpdate,
    DemoResponse,
    DemoUpdate,
    OperationResponse,
)
from app.services import DemoService
from app.repositories.auth import AccessRepository
from app.security import (
    AuthContext,
    authorize_vehicle,
    get_auth_context,
    require_allowed_command,
    require_demo_access,
    require_vehicle_access,
)


router = APIRouter(prefix="/demos", tags=["Demos"])
service = DemoService()
access_repository = AccessRepository()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


def _reject_guest(context: AuthContext) -> None:
    if "INVITADO" in context.roles:
        raise HTTPException(status_code=403, detail="El modo invitado solo puede ejecutar demos de empresa.")


@router.post(
    "/",
    response_model=DemoCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear demo",
)
def crear_demo(body: DemoCreate, context: AuthContext = Depends(get_auth_context)) -> DemoCreateResponse:
    try:
        _reject_guest(context)
        authorize_vehicle(context, body.id_vehiculo)
        rows = service.create(body.id_vehiculo, body.nombre, body.descripcion)
        if not rows or rows[0].get("id_demo") is None:
            raise HTTPException(
                status_code=500,
                detail="sp_crear_demo no devolvió id_demo",
            )
        return rows[0]
    except Exception as exc:
        raise _db_error(exc) from exc


@router.get("/vehiculo/{id_vehiculo}", response_model=list[DemoResponse], summary="Listar demos del vehículo")
def obtener_demos(
    id_vehiculo: int = Path(..., gt=0),
    context: AuthContext = Depends(require_vehicle_access),
):
    try:
        rows = service.list_for_vehicle(id_vehiculo)
        if "INVITADO" not in context.roles:
            return rows
        return [row for row in rows if access_repository.is_company_demo(int(row["id_demo"]))]
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put("/{id_demo}", response_model=OperationResponse, summary="Actualizar demo")
def actualizar_demo(
    id_demo: int = Path(..., gt=0),
    body: DemoUpdate = ...,
    context: AuthContext = Depends(require_demo_access),
):
    try:
        _reject_guest(context)
        service.update(id_demo, body.nombre, body.descripcion, body.activo)
        return {"message": "Operación realizada correctamente", "id": id_demo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.delete("/{id_demo}", response_model=OperationResponse, summary="Eliminar demo")
def eliminar_demo(
    id_demo: int = Path(..., gt=0),
    context: AuthContext = Depends(require_demo_access),
):
    try:
        _reject_guest(context)
        service.delete(id_demo)
        return {"message": "Demo eliminada correctamente", "id": id_demo}
    except Exception as exc:
        raise _db_error(exc) from exc


@router.post(
    "/movimiento",
    response_model=DemoMovimientoCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar movimiento a una demo",
)
def agregar_movimiento_demo(
    body: DemoMovimientoCreate,
    context: AuthContext = Depends(get_auth_context),
) -> DemoMovimientoCreateResponse:
    try:
        _reject_guest(context)
        vehicle_id = access_repository.demo_vehicle(body.id_demo)
        if vehicle_id is None:
            raise HTTPException(status_code=404, detail="Demo no encontrada.")
        authorize_vehicle(context, vehicle_id)
        require_allowed_command(vehicle_id, body.id_comando)
        service.add_movement(
            body.id_demo,
            body.id_comando,
            body.orden,
            body.duracion_ms,
            body.pausa_ms,
        )
        return DemoMovimientoCreateResponse(
            message="Movimiento agregado correctamente"
        )
    except Exception as exc:
        raise _db_error(exc) from exc


# Compatibilidad con el plural de la primera versión; la ruta documentada es
# /demos/movimiento, que coincide con la firma actual de la práctica.
router.add_api_route(
    "/movimientos",
    agregar_movimiento_demo,
    methods=["POST"],
    response_model=DemoMovimientoCreateResponse,
    include_in_schema=False,
)


@router.get("/{id_demo}/movimientos", response_model=list[DemoMovimientoResponse], summary="Listar movimientos de una demo")
def obtener_movimientos_demo(
    id_demo: int = Path(..., gt=0),
    _context: AuthContext = Depends(require_demo_access),
):
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
    context: AuthContext = Depends(get_auth_context),
):
    try:
        _reject_guest(context)
        vehicle_id = access_repository.movement_vehicle(id_demo_movimiento)
        if vehicle_id is None:
            raise HTTPException(status_code=404, detail="Movimiento de demo no encontrado.")
        authorize_vehicle(context, vehicle_id)
        require_allowed_command(vehicle_id, body.id_comando)
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
def eliminar_movimiento_demo(
    id_demo_movimiento: int = Path(..., gt=0),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        _reject_guest(context)
        vehicle_id = access_repository.movement_vehicle(id_demo_movimiento)
        if vehicle_id is None:
            raise HTTPException(status_code=404, detail="Movimiento de demo no encontrado.")
        authorize_vehicle(context, vehicle_id)
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
