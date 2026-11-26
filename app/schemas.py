"""Modelos Pydantic v2 para los 21 stored procedures de la API."""

from datetime import datetime
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class InputModel(BaseModel):
    """Configuración común para cuerpos de entrada de la API."""

    model_config = ConfigDict(extra="forbid")


class OutputModel(BaseModel):
    """Conserva columnas adicionales devueltas por los stored procedures."""

    model_config = ConfigDict(from_attributes=True, extra="allow")


class DatabaseHealthResponse(BaseModel):
    """Respuesta cuando la instancia MySQL/RDS responde correctamente."""

    status: Literal["ok"] = "ok"
    rds: Literal["connected"] = "connected"
    database: Literal["mysql"] = "mysql"


class DatabaseHealthErrorResponse(BaseModel):
    """Respuesta segura cuando no se puede verificar la instancia RDS."""

    status: Literal["error"] = "error"
    rds: Literal["disconnected"] = "disconnected"
    detail: str


# ── Vehículos ─────────────────────────────────────────────────────────────────

class VehiculoCreate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    modelo: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=500)
    microcontrolador: str = Field(..., min_length=1, max_length=100)


class VehiculoUpdate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    modelo: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=500)
    microcontrolador: str = Field(..., min_length=1, max_length=100)
    activo: bool


class VehiculoResponse(OutputModel):
    id_vehiculo: int | None = None
    nombre: str | None = None
    modelo: str | None = None
    descripcion: str | None = None
    microcontrolador: str | None = None
    activo: bool | None = None


class VehiculoCreateResponse(BaseModel):
    """Respuesta exclusiva de ``POST /vehiculos/`` (LAST_INSERT_ID)."""

    id_vehiculo: int


# ── Comandos ──────────────────────────────────────────────────────────────────

class ComandoCreate(InputModel):
    id_vehiculo: int = Field(..., gt=0)
    nombre: str = Field(..., min_length=1, max_length=100)
    codigo: int = Field(..., ge=0, le=65535)
    descripcion: str = Field(..., min_length=1, max_length=500)


class ComandoUpdate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    codigo: int = Field(..., ge=0, le=65535)
    descripcion: str = Field(..., min_length=1, max_length=500)
    activo: bool


class ComandoResponse(OutputModel):
    id_comando: int | None = None
    id_vehiculo: int | None = None
    nombre: str | None = None
    codigo: int | None = None
    descripcion: str | None = None
    activo: bool | None = None


class ComandoCreadoResponse(OutputModel):
    message: str
    id_comando: int


# ── Estado ────────────────────────────────────────────────────────────────────

class EstadoUpdate(InputModel):
    id_comando: int = Field(..., gt=0)
    conectado: bool


class EstadoResponse(OutputModel):
    id_vehiculo: int | None = None
    id_comando: int | None = None
    conectado: bool | None = None
    fecha_hora: datetime | None = None


# ── Historial / Pruebas 1 y 2 ──────────────────────────────────────────────────

class ComandoEnviar(InputModel):
    """Body de POST /vehiculos/{id_vehiculo}/comando."""

    id_comando: int = Field(..., gt=0, description="ID del comando a ejecutar")
    conectado: bool = Field(..., description="Estado de conexión del vehículo")
    origen: str = Field("MANUAL", min_length=1, max_length=30, description="Origen del movimiento")


class ComandoResponseMovimiento(OutputModel):
    message: str
    id_vehiculo: int
    id_comando: int
    conectado: bool
    origen: str


class HistorialItem(OutputModel):
    id_historial: int | None = None
    id_vehiculo: int | None = None
    comando: str | None = None
    codigo: int | None = None
    id_comando: int | None = None
    fecha_hora: datetime | None = None
    origen: str | None = None


# ── Demos ─────────────────────────────────────────────────────────────────────

class DemoCreate(InputModel):
    id_vehiculo: int = Field(..., gt=0)
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=500)


class DemoUpdate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=500)
    activo: bool


class DemoResponse(OutputModel):
    id_demo: int | None = None
    id_vehiculo: int | None = None
    nombre: str | None = None
    descripcion: str | None = None
    activo: bool | None = None


class DemoCreateResponse(BaseModel):
    """Respuesta exclusiva de ``POST /demos/`` (LAST_INSERT_ID)."""

    id_demo: int


class DemoMovimientoCreate(InputModel):
    id_demo: int = Field(..., gt=0)
    id_comando: int = Field(..., gt=0)
    orden: int = Field(..., ge=1)
    duracion_ms: int = Field(..., ge=0, le=86_400_000)
    pausa_ms: int = Field(..., ge=0, le=86_400_000)


class DemoMovimientoUpdate(InputModel):
    id_comando: int = Field(..., gt=0)
    orden: int = Field(..., ge=1)
    duracion_ms: int = Field(..., ge=0, le=86_400_000)
    pausa_ms: int = Field(..., ge=0, le=86_400_000)


class DemoMovimientoResponse(OutputModel):
    id_demo_movimiento: int | None = None
    id_demo: int | None = None
    orden: int | None = None
    id_comando: int | None = None
    comando: str | None = None
    codigo: int | None = None
    duracion_ms: int | None = None
    pausa_ms: int | None = None


class DemoMovimientoCreateResponse(BaseModel):
    """Confirmación de inserción, cuyo procedimiento no retorna filas."""

    message: str


class DemoEjecucionRequest(InputModel):
    id_demo: int = Field(..., gt=0, description="ID de la demo que se ejecutará")
    id_vehiculo: int | None = Field(
        None,
        gt=0,
        description="ID del vehículo; puede omitirse si lo devuelve el stored procedure",
    )


class DemoEjecucionResponse(OutputModel):
    message: str
    id_demo: int
    id_vehiculo: int
    total_movimientos: int
    movimientos_ejecutados: int


class OperationResponse(OutputModel):
    message: str
    id: int | None = None


# ── Administración / Etapa 3 ─────────────────────────────────────────────────

class PageQuery(BaseModel):
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ModeloAdminCreate(InputModel):
    clave: str = Field(..., min_length=1, max_length=64)
    nombre: str = Field(..., min_length=1, max_length=120)
    descripcion: str | None = Field(None, max_length=500)
    microcontrolador: str | None = Field(None, max_length=100)
    activo: bool = True


class ModeloAdminUpdate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    descripcion: str | None = Field(None, max_length=500)
    microcontrolador: str | None = Field(None, max_length=100)
    activo: bool


class ModeloAdminResponse(OutputModel):
    id_modelo: int
    clave: str
    nombre: str
    descripcion: str | None = None
    microcontrolador: str | None = None
    activo: bool


class UnidadAdminCreate(InputModel):
    id_modelo: int = Field(..., gt=0)
    identificador_unico: str = Field(..., min_length=1, max_length=80)
    nombre: str = Field(..., min_length=1, max_length=80)
    descripcion: str | None = Field(None, max_length=255)
    estado_inventario: Literal[
        "INVENTARIO", "EXHIBICION", "VENDIDA", "MANTENIMIENTO", "BAJA"
    ] = "INVENTARIO"
    activo: bool = True


class UnidadAdminUpdate(InputModel):
    id_modelo: int = Field(..., gt=0)
    identificador_unico: str = Field(..., min_length=1, max_length=80)
    estado_inventario: Literal[
        "INVENTARIO", "EXHIBICION", "VENDIDA", "MANTENIMIENTO", "BAJA"
    ]


class UnidadAdminResponse(OutputModel):
    id_vehiculo: int
    id_modelo: int
    identificador_unico: str
    estado_inventario: str
    nombre: str | None = None
    legacy_modelo: str | None = None
    descripcion: str | None = None
    microcontrolador: str | None = None
    activo: bool | None = None
    modelo_clave: str | None = None
    modelo_nombre: str | None = None


class ClienteAdminCreate(InputModel):
    email: str = Field(..., min_length=3, max_length=254)
    nombre: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=12, max_length=128)
    activo: bool = True
    email_verificado: bool = False


class ClienteAdminUpdate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    activo: bool
    email_verificado: bool


class ClienteAdminResponse(OutputModel):
    id_usuario: int
    email: str
    nombre: str
    activo: bool
    email_verificado: bool


class AsignacionCreate(InputModel):
    id_vehiculo: int = Field(..., gt=0)
    id_usuario: int = Field(..., gt=0)
    motivo: str | None = Field(None, max_length=255)


class AsignacionResponse(OutputModel):
    id_asignacion: int
    id_vehiculo: int
    id_usuario: int
    tipo: str
    estado: str
    inicia_en: datetime
    finaliza_en: datetime | None = None
    motivo: str | None = None
    email: str | None = None
    usuario_nombre: str | None = None
    vehiculo_nombre: str | None = None


class AsignacionRevocar(InputModel):
    motivo: str | None = Field(None, max_length=255)


class AuditoriaResponse(OutputModel):
    id_auditoria: int
    id_usuario: int | None = None
    actor_tipo: str
    accion: str
    recurso_tipo: str
    recurso_id: str | None = None
    detalle: dict | None = None
    creado_en: datetime

    @field_validator("detalle", mode="before")
    @classmethod
    def parse_detalle(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {"raw": value}
        return value


class DashboardResponse(BaseModel):
    vehiculos: int
    unidades_vehiculo: int
    usuarios: int
    asignaciones_vehiculo: int
    demos: int
    auditoria: int


class MiVehiculoResponse(OutputModel):
    id_asignacion: int
    id_usuario: int
    id_vehiculo: int
    estado: str
    inicia_en: datetime
    finaliza_en: datetime | None = None
    vehiculo_nombre: str
    identificador_unico: str
    estado_inventario: str
    id_modelo: int
    modelo_clave: str
    modelo_nombre: str
    acceso_tipo: str = "PROPIETARIO"


class SupportAdminResponse(OutputModel):
    id_usuario: int
    nombre: str
    email: str


class PrivateDemoCreate(InputModel):
    id_vehiculo: int = Field(..., gt=0)
    nombre: str = Field(..., min_length=1, max_length=80)
    descripcion: str | None = Field(None, max_length=255)
    duracion_max_ms: int = Field(300000, ge=1, le=300000)
    max_pasos: int = Field(100, ge=1, le=100)


class PrivateDemoUpdate(InputModel):
    nombre: str = Field(..., min_length=1, max_length=80)
    descripcion: str | None = Field(None, max_length=255)
    activo: bool = True
    duracion_max_ms: int = Field(300000, ge=1, le=300000)
    max_pasos: int = Field(100, ge=1, le=100)


class PrivateDemoResponse(OutputModel):
    id_demo: int
    id_vehiculo: int
    nombre: str
    descripcion: str | None = None
    activo: bool
    alcance: str
    id_usuario: int
    duracion_max_ms: int
    max_pasos: int
    pasos: int = 0
    duracion_total_ms: int = 0


class PrivateDemoMovementCreate(InputModel):
    id_comando: int = Field(..., gt=0)
    orden: int = Field(..., ge=1, le=100)
    duracion_ms: int = Field(..., ge=0, le=300000)
    pausa_ms: int = Field(0, ge=0, le=300000)


class PrivateDemoMovementUpdate(PrivateDemoMovementCreate):
    pass


class ModeloComandoPatch(InputModel):
    permitido: bool


class ModeloComandoResponse(OutputModel):
    id_modelo: int
    id_comando: int
    codigo: int
    nombre: str
    permitido: bool


class GuestVehicleResponse(OutputModel):
    id_vehiculo: int
    vehiculo_nombre: str
    identificador_unico: str
    id_modelo: int
    modelo_clave: str
    modelo_nombre: str
    estado: str
    libera_en: datetime | None = None


class GuestSessionCreate(InputModel):
    id_vehiculo: int = Field(..., gt=0)


class GuestSessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 300
    id_vehiculo: int
    id_sesion_invitado: int
    expira_en: datetime


# ── Autenticación / Etapa 4 ───────────────────────────────────────────────────

class LoginRequest(InputModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(InputModel):
    refresh_token: str = Field(..., min_length=20, max_length=4096)


class LogoutRequest(InputModel):
    refresh_token: str | None = Field(None, min_length=20, max_length=4096)


class UserSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AuthUserResponse(BaseModel):
    id_usuario: int
    email: str
    nombre: str
    roles: list[str]
    activo: bool
    email_verificado: bool


class SupportAuthorizationCreate(InputModel):
    id_admin: int = Field(..., gt=0)
    motivo: str = Field(..., min_length=1, max_length=255)


class SupportAuthorizationResponse(OutputModel):
    id_autorizacion: int
    id_vehiculo: int
    id_propietario: int
    id_admin: int
    motivo: str
    creado_en: datetime
    expira_en: datetime
    revocada_en: datetime | None = None
    estado: str
