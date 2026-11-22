"""Recursos privados del usuario autenticado."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.schemas import MiVehiculoResponse, SupportAdminResponse
from app.schemas import (
    OperationResponse,
    SupportAuthorizationCreate,
    SupportAuthorizationResponse,
)
from app.security import AuthContext, authorize_vehicle, require_user_or_admin
from app.services_admin import AdminService, SupportService


router = APIRouter(
    prefix="/me",
    tags=["Mis recursos"],
    responses={
        401: {"description": "Autenticación requerida."},
        403: {"description": "El contexto autenticado no tiene permisos."},
        422: {"description": "Error de validación del contrato."},
    },
)
service = AdminService()
support_service = SupportService()


@router.get("/vehiculos", response_model=list[MiVehiculoResponse])
def mis_vehiculos(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return service.list_my_vehicles(
        context.user_id,
        limit,
        offset,
        include_support="ADMIN" in context.roles,
    )


@router.get("/soporte/admins", response_model=list[SupportAdminResponse])
def listar_admins_soporte(
    _context: AuthContext = Depends(require_user_or_admin),
):
    return service.list_admins()


@router.get(
    "/vehiculos/{id_vehiculo}/soporte",
    response_model=list[SupportAuthorizationResponse],
    responses={403: {"description": "Solo el propietario puede consultar autorizaciones."}},
)
def listar_soporte(
    id_vehiculo: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    resource = authorize_vehicle(context, id_vehiculo)
    if "USUARIO" not in context.roles or not bool(resource["es_propietario"]):
        raise HTTPException(status_code=403, detail="Solo el propietario activo puede consultar soporte.")
    return support_service.list_for_owner(id_vehiculo, int(context.user_id))


@router.post(
    "/vehiculos/{id_vehiculo}/soporte",
    response_model=SupportAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"description": "Solo el propietario puede otorgar soporte."}, 409: {"description": "Ya existe soporte activo."}},
)
def otorgar_soporte(
    body: SupportAuthorizationCreate,
    id_vehiculo: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    return support_service.create_for_owner(
        id_vehiculo,
        int(context.user_id),
        body.id_admin,
        body.motivo,
    )


@router.delete(
    "/vehiculos/{id_vehiculo}/soporte/{id_autorizacion}",
    response_model=OperationResponse,
    responses={403: {"description": "Solo el propietario puede revocar soporte."}},
)
def revocar_soporte(
    id_vehiculo: int = Path(..., gt=0),
    id_autorizacion: int = Path(..., gt=0),
    context: AuthContext = Depends(require_user_or_admin),
):
    resource = authorize_vehicle(context, id_vehiculo)
    if "USUARIO" not in context.roles or not bool(resource["es_propietario"]):
        raise HTTPException(status_code=403, detail="Solo el propietario activo puede revocar soporte.")
    return support_service.revoke_for_owner(id_autorizacion, int(context.user_id))
