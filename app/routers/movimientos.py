"""Endpoints de las Pruebas Funcionales 1 y 2."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path

from app.routers.hardware_ws import manager
from app.schemas import ComandoEnviar, ComandoResponseMovimiento, HistorialItem
from app.services import HistoryService

router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])
service = HistoryService()


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=500, detail=f"Error de base de datos: {exc}")


# ── Prueba 1: POST /vehiculos/{id_vehiculo}/comando ────────────────────────────

@router.post(
    "/{id_vehiculo}/comando",
    response_model=ComandoResponseMovimiento,
    status_code=201,
    summary="[Prueba 1] Registrar movimiento individual en estado e historial",
)
async def enviar_comando(
    id_vehiculo: int = Path(..., gt=0, description="ID del vehículo"),
    body: ComandoEnviar = ...,
):
    """
    Envía un comando a un vehículo realizando dos operaciones en BD:

    1. **sp_actualizar_estado** — persiste el comando actual en `estado_vehiculo`
       (INSERT … ON DUPLICATE KEY UPDATE).
    2. **sp_registrar_historial** — inserta un nuevo registro en `historial_comandos`.

    Las dos llamadas se ejecutan en una única transacción MySQL. Si cualquiera
    falla, el estado y el historial se revierten juntos.
    """
    try:
        await asyncio.to_thread(
            service.send_command_transactionally,
            id_vehiculo,
            body.id_comando,
            body.conectado,
            body.origen,
        )

        evento_ws = {
            "event": "nuevo_movimiento",
            "id_vehiculo": id_vehiculo,
            "id_comando": body.id_comando,
            "conectado": body.conectado,
            "origen": body.origen,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await manager.broadcast_to_vehicle(id_vehiculo, evento_ws)

        return ComandoResponseMovimiento(
            message="Comando registrado correctamente",
            id_vehiculo=id_vehiculo,
            id_comando=body.id_comando,
            conectado=body.conectado,
            origen=body.origen,
        )
    except Exception as exc:
        raise _db_error(exc) from exc


# ── Prueba 2: GET /vehiculos/{id_vehiculo}/historial ──────────────────────────

@router.get(
    "/{id_vehiculo}/historial",
    response_model=list[HistorialItem],
    summary="[Prueba 2] Últimos 10 movimientos del vehículo",
)
def obtener_historial(
    id_vehiculo: int = Path(..., gt=0, description="ID del vehículo"),
):
    """
    Retorna los **últimos 10 movimientos** registrados para el vehículo.

    Llama a **sp_obtener_historial** (ordenado por fecha_hora DESC,
    id_historial DESC) y recorta a 10 registros en Python, ya que el
    stored procedure no incluye LIMIT.
    """
    try:
        return service.list(id_vehiculo, limit=10)
    except Exception as exc:
        raise _db_error(exc) from exc
