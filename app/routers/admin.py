"""Rutas administrativas de la Etapa 3.

Todas requieren un contexto ADMIN emitido por la futura autenticación. La
dependencia actual responde 401, evitando exponer CRUD mientras la Etapa 4 no
esté instalada.
"""

from fastapi import APIRouter, Depends, Path, Query, status

from app.schemas import (
    AsignacionCreate,
    AsignacionResponse,
    AsignacionRevocar,
    AuditoriaResponse,
    ClienteAdminCreate,
    ClienteAdminResponse,
    ClienteAdminUpdate,
    DashboardResponse,
    ModeloAdminCreate,
    ModeloAdminResponse,
    ModeloAdminUpdate,
    ModeloComandoPatch,
    ModeloComandoResponse,
    OperationResponse,
    UnidadAdminCreate,
    UnidadAdminResponse,
    UnidadAdminUpdate,
)
from app.security import AuthContext, require_admin
from app.services_admin import AdminService


router = APIRouter(
    prefix="/admin",
    tags=["Administración"],
    responses={
        401: {"description": "Autenticación requerida."},
        403: {"description": "El contexto autenticado no tiene el rol requerido."},
        404: {"description": "Recurso no encontrado."},
        409: {"description": "Conflicto de integridad o recurso activo duplicado."},
        422: {"description": "Error de validación del contrato."},
    },
)
service = AdminService()


@router.get("/dashboard", response_model=DashboardResponse, dependencies=[Depends(require_admin)])
def dashboard() -> DashboardResponse:
    return service.dashboard()


@router.get("/modelos", response_model=list[ModeloAdminResponse], dependencies=[Depends(require_admin)])
def listar_modelos(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=120),
):
    return service.list_models(limit, offset, search)


@router.post(
    "/modelos",
    response_model=ModeloAdminResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def crear_modelo(body: ModeloAdminCreate):
    return service.create_model(body.model_dump())


@router.put("/modelos/{id_modelo}", response_model=ModeloAdminResponse, dependencies=[Depends(require_admin)])
def actualizar_modelo(
    body: ModeloAdminUpdate,
    id_modelo: int = Path(..., gt=0),
):
    return service.update_model(id_modelo, body.model_dump())


@router.patch(
    "/modelos/{id_modelo}/comandos/{id_comando}",
    response_model=ModeloComandoResponse,
    dependencies=[Depends(require_admin)],
)
def actualizar_capacidad_comando(
    body: ModeloComandoPatch,
    id_modelo: int = Path(..., gt=0),
    id_comando: int = Path(..., gt=0),
):
    return service.update_model_command(id_modelo, id_comando, body.permitido)


@router.get(
    "/modelos/{id_modelo}/comandos",
    response_model=list[ModeloComandoResponse],
    dependencies=[Depends(require_admin)],
)
def listar_capacidades_comando(id_modelo: int = Path(..., gt=0)):
    return service.list_model_commands(id_modelo)


@router.get("/unidades", response_model=list[UnidadAdminResponse], dependencies=[Depends(require_admin)])
def listar_unidades(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    estado: str | None = Query(None),
):
    return service.list_units(limit, offset, estado)


@router.post(
    "/unidades",
    response_model=UnidadAdminResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def crear_unidad(body: UnidadAdminCreate):
    return service.create_unit(body.model_dump())


@router.put("/unidades/{id_vehiculo}", response_model=UnidadAdminResponse, dependencies=[Depends(require_admin)])
def actualizar_unidad(
    body: UnidadAdminUpdate,
    id_vehiculo: int = Path(..., gt=0),
):
    return service.update_unit(id_vehiculo, body.model_dump())


@router.get("/clientes", response_model=list[ClienteAdminResponse], dependencies=[Depends(require_admin)])
def listar_clientes(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=254),
):
    return service.list_clients(limit, offset, search)


@router.post(
    "/clientes",
    response_model=ClienteAdminResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def crear_cliente(body: ClienteAdminCreate):
    return service.create_client(body.model_dump())


@router.put("/clientes/{id_usuario}", response_model=ClienteAdminResponse, dependencies=[Depends(require_admin)])
def actualizar_cliente(
    body: ClienteAdminUpdate,
    id_usuario: int = Path(..., gt=0),
):
    return service.update_client(id_usuario, body.model_dump())


@router.get("/asignaciones", response_model=list[AsignacionResponse], dependencies=[Depends(require_admin)])
def listar_asignaciones(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    id_vehiculo: int | None = Query(None, gt=0),
):
    return service.list_assignments(limit, offset, id_vehiculo)


@router.post(
    "/asignaciones",
    response_model=AsignacionResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_asignacion(body: AsignacionCreate, context: AuthContext = Depends(require_admin)):
    return service.create_assignment(body.model_dump(), context.user_id)


@router.post(
    "/asignaciones/{id_asignacion}/revocar",
    response_model=OperationResponse,
    dependencies=[Depends(require_admin)],
)
def revocar_asignacion(
    body: AsignacionRevocar,
    id_asignacion: int = Path(..., gt=0),
):
    return service.revoke_assignment(id_asignacion, body.motivo)


@router.get("/auditoria", response_model=list[AuditoriaResponse], dependencies=[Depends(require_admin)])
def listar_auditoria(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    recurso_tipo: str | None = Query(None, max_length=60),
):
    return service.list_audit(limit, offset, recurso_tipo)
