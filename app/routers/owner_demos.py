"""CRUD de demos privadas del propietario activo."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.schemas import (
    DemoMovimientoResponse,
    OperationResponse,
    PrivateDemoCreate,
    PrivateDemoMovementCreate,
    PrivateDemoMovementUpdate,
    PrivateDemoResponse,
    PrivateDemoUpdate,
)
from app.security import AuthContext, require_user_or_admin
from app.services_owner import OwnerDemoService


router = APIRouter(prefix="/me/demos", tags=["Mis demos"])
service = OwnerDemoService()


def owner_context(context: AuthContext) -> AuthContext:
    if context.user_id is None or "USUARIO" not in context.roles:
        raise HTTPException(status_code=403, detail="Solo el propietario puede gestionar demos privadas.")
    return context


@router.get("", response_model=list[PrivateDemoResponse])
def listar_demos(
    id_vehiculo: int | None = Query(None, gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return service.list(owner_context(context).user_id, id_vehiculo)


@router.post("", response_model=PrivateDemoResponse, status_code=status.HTTP_201_CREATED)
def crear_demo(body: PrivateDemoCreate, context: AuthContext = Depends(require_user_or_admin)):
    context = owner_context(context)
    return service.create(context.user_id, body.model_dump())


@router.get("/{id_demo}", response_model=PrivateDemoResponse)
def obtener_demo(id_demo: int = Path(..., gt=0), context: AuthContext = Depends(require_user_or_admin)):
    return service.get(owner_context(context).user_id, id_demo)


@router.put("/{id_demo}", response_model=PrivateDemoResponse)
def actualizar_demo(
    body: PrivateDemoUpdate,
    id_demo: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return service.update(owner_context(context).user_id, id_demo, body.model_dump())


@router.delete("/{id_demo}", response_model=OperationResponse)
def eliminar_demo(id_demo: int = Path(..., gt=0), context: AuthContext = Depends(require_user_or_admin)):
    return service.delete(owner_context(context).user_id, id_demo)


@router.get("/{id_demo}/movimientos", response_model=list[DemoMovimientoResponse])
def listar_movimientos(id_demo: int = Path(..., gt=0), context: AuthContext = Depends(require_user_or_admin)):
    return service.movements(owner_context(context).user_id, id_demo)


@router.post("/{id_demo}/movimientos", response_model=DemoMovimientoResponse, status_code=status.HTTP_201_CREATED)
def agregar_movimiento(
    body: PrivateDemoMovementCreate,
    id_demo: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return service.add_movement(owner_context(context).user_id, id_demo, body.model_dump())


@router.put("/movimientos/{id_demo_movimiento}", response_model=DemoMovimientoResponse)
def actualizar_movimiento(
    body: PrivateDemoMovementUpdate,
    id_demo_movimiento: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return service.update_movement(owner_context(context).user_id, id_demo_movimiento, body.model_dump())


@router.delete("/movimientos/{id_demo_movimiento}", response_model=OperationResponse)
def eliminar_movimiento(
    id_demo_movimiento: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return service.delete_movement(owner_context(context).user_id, id_demo_movimiento)
