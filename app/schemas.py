"""
Schemas Pydantic v2 para validación de request/response de la API.
Requiere pydantic>=2.14 (tiene wheel para Python 3.14).
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Prueba 1: POST /vehiculos/{id_vehiculo}/comando ────────────────────────────

class ComandoEnviar(BaseModel):
    """Body para POST /vehiculos/{id_vehiculo}/comando"""
    id_comando: int   = Field(..., description="ID del comando a ejecutar")
    conectado:  bool  = Field(True, description="Estado de conexión del vehículo")
    origen:     str   = Field("api", description="Origen: 'api', 'ws', 'manual'")


class ComandoResponse(BaseModel):
    """Respuesta exitosa al enviar un comando."""
    message:     str
    id_vehiculo: int
    id_comando:  int
    conectado:   bool
    origen:      str


# ── Prueba 2: GET /vehiculos/{id_vehiculo}/historial ───────────────────────────

class HistorialItem(BaseModel):
    """Un registro del historial de comandos."""
    id_historial: int
    id_vehiculo:  int
    comando:      Optional[str] = None
    codigo:       Optional[int] = None
    fecha_hora:   datetime
    origen:       Optional[str] = None

    model_config = {"from_attributes": True}
