"""Ejecución HTTP de demos sobre el WebSocket global del vehículo."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.routers.hardware_ws import manager
from app.schemas import DemoEjecucionRequest, DemoEjecucionResponse
from app.services import DemoService, StateService

router = APIRouter(prefix="/demos", tags=["Demos"])
logger = logging.getLogger(__name__)
demo_service = DemoService()
state_service = StateService()
_vehicle_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    logger.exception("Error al ejecutar demo", exc_info=exc)
    return HTTPException(status_code=500, detail=f"Error al ejecutar la demo: {exc}")


def _vehicle_id(body_id: int | None, movements: list[dict[str, Any]]) -> int:
    id_vehiculo = body_id
    if id_vehiculo is None:
        for movement in movements:
            id_vehiculo = movement.get("id_vehiculo") or movement.get("vehiculo_id")
            if id_vehiculo is not None:
                break

    if isinstance(id_vehiculo, bool) or not isinstance(id_vehiculo, int) or id_vehiculo <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere id_vehiculo en el cuerpo o en el resultado de la demo",
        )

    for movement in movements:
        for item in ("id_vehiculo", "vehiculo_id"):
            returned_id = movement.get(item)
            if returned_id is not None and returned_id != id_vehiculo:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El vehículo indicado no coincide con el vehículo asociado a la demo",
                )
    return id_vehiculo


@router.post(
    "/ejecutar",
    response_model=DemoEjecucionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ejecutar demo en el vehículo sin registrar historial",
)
async def ejecutar_demo(body: DemoEjecucionRequest) -> DemoEjecucionResponse:
    """Reproduce movimientos ordenados y los publica en el canal del vehículo."""
    try:
        movimientos = await asyncio.to_thread(demo_service.list_movements, body.id_demo)
        if not movimientos:
            raise HTTPException(status_code=404, detail="La demo no tiene movimientos")

        movimientos = sorted(movimientos, key=lambda movimiento: movimiento["orden"])
        id_vehiculo = _vehicle_id(body.id_vehiculo, movimientos)

        # Evita enviar una secuencia a un vehículo distinto por datos inconsistentes.
        for movimiento in movimientos:
            for key in ("id_vehiculo", "vehiculo_id"):
                row_vehicle_id = movimiento.get(key)
                if row_vehicle_id is not None and row_vehicle_id != id_vehiculo:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="La demo contiene movimientos asociados a vehículos distintos",
                    )

        total = len(movimientos)
        async with _vehicle_locks[id_vehiculo]:
            if manager.connection_count(id_vehiculo) == 0:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"No hay una conexión WebSocket activa para el vehículo {id_vehiculo}",
                )

            executed = 0
            for index, movimiento in enumerate(movimientos, start=1):
                event = {
                    "event": "nuevo_movimiento",
                    "id_demo": body.id_demo,
                    "id_vehiculo": id_vehiculo,
                    "paso": index,
                    "total": total,
                    "orden": movimiento["orden"],
                    "id_comando": movimiento["id_comando"],
                    "comando": movimiento.get("comando"),
                    "codigo": movimiento.get("codigo"),
                    "conectado": True,
                    "origen": "DEMO",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "duracion_ms": movimiento["duracion_ms"],
                    "pausa_ms": movimiento["pausa_ms"],
                }

                delivered = await manager.broadcast_to_vehicle(id_vehiculo, event)
                if delivered == 0:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"No se pudo enviar el movimiento {index} al vehículo {id_vehiculo}",
                    )

                # Esta ruta solo actualiza estado: nunca invoca historial.
                await asyncio.to_thread(
                    state_service.update,
                    id_vehiculo,
                    movimiento["id_comando"],
                    True,
                )
                executed += 1

                await asyncio.sleep(movimiento["duracion_ms"] / 1000)
                if index < total and movimiento["pausa_ms"] > 0:
                    await asyncio.sleep(movimiento["pausa_ms"] / 1000)

        return DemoEjecucionResponse(
            message="Ejecución de DEMO completada correctamente",
            id_demo=body.id_demo,
            id_vehiculo=id_vehiculo,
            total_movimientos=total,
            movimientos_ejecutados=executed,
        )
    except Exception as exc:
        raise _db_error(exc) from exc
