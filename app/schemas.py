"""Modelos Pydantic v2 para los 21 stored procedures de la API."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class InputModel(BaseModel):
    """Configuración común para cuerpos de entrada de la API."""

    model_config = ConfigDict(extra="forbid")


class OutputModel(BaseModel):
    """Conserva columnas adicionales devueltas por los stored procedures."""

    model_config = ConfigDict(from_attributes=True, extra="allow")


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
