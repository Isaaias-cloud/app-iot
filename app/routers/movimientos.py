"""
Router REST para las Pruebas 1 y 2.

Prueba 1 — POST /vehiculos/{id_vehiculo}/comando
    Registra un movimiento individual:
      · sp_actualizar_estado  → actualiza/inserta en estado_vehiculo
      · sp_registrar_historial → inserta en historial_comandos

Prueba 2 — GET /vehiculos/{id_vehiculo}/historial
    Retorna los últimos 10 movimientos del vehículo:
      · sp_obtener_historial retorna todos ordenados DESC
      · Se recortan a 10 en Python (el SP no tiene LIMIT)
"""

from typing import List
from fastapi import APIRouter, HTTPException, Path
from app.database import call_procedure
from app.schemas import ComandoEnviar, ComandoResponse, HistorialItem

router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])


# ── Prueba 1: POST /vehiculos/{id_vehiculo}/comando ────────────────────────────

@router.post(
    "/{id_vehiculo}/comando",
    response_model=ComandoResponse,
    status_code=201,
    summary="[Prueba 1] Registrar movimiento individual en estado e historial",
)
def enviar_comando(
    id_vehiculo: int = Path(..., description="ID del vehículo"),
    body: ComandoEnviar = ...,
):
    """
    Envía un comando a un vehículo realizando dos operaciones en BD:

    1. **sp_actualizar_estado** — persiste el comando actual en `estado_vehiculo`
       (INSERT … ON DUPLICATE KEY UPDATE).
    2. **sp_registrar_historial** — inserta un nuevo registro en `historial_comandos`.

    Ambas son atómicas desde el punto de vista del cliente: si cualquiera falla
    se devuelve HTTP 500.
    """
    try:
        # 1. Actualizar estado actual del vehículo
        call_procedure(
            "sp_actualizar_estado",
            (id_vehiculo, body.id_comando, body.conectado),
        )

        # 2. Registrar en historial
        call_procedure(
            "sp_registrar_historial",
            (id_vehiculo, body.id_comando, body.origen),
        )

        return ComandoResponse(
            message="Comando registrado correctamente",
            id_vehiculo=id_vehiculo,
            id_comando=body.id_comando,
            conectado=body.conectado,
            origen=body.origen,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Prueba 2: GET /vehiculos/{id_vehiculo}/historial ──────────────────────────

@router.get(
    "/{id_vehiculo}/historial",
    response_model=List[HistorialItem],
    summary="[Prueba 2] Últimos 10 movimientos del vehículo",
)
def obtener_historial(
    id_vehiculo: int = Path(..., description="ID del vehículo"),
):
    """
    Retorna los **últimos 10 movimientos** registrados para el vehículo.

    Llama a **sp_obtener_historial** (ordenado por fecha_hora DESC,
    id_historial DESC) y recorta a 10 registros en Python, ya que el
    stored procedure no incluye LIMIT.
    """
    try:
        rows = call_procedure("sp_obtener_historial", (id_vehiculo,))
        # sp_obtener_historial ya ordena DESC; tomamos los primeros 10
        return rows[:10]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
