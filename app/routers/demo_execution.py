"""Ejecución HTTP de demos sobre el WebSocket global del vehículo."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.routers.hardware_ws import manager
from app.repositories.auth import AccessRepository
from app.repositories.owner_demos import OwnerDemoRepository
from app.schemas import DemoEjecucionRequest, DemoEjecucionResponse
from app.security import AuthContext, authorize_vehicle, get_auth_context
from app.services import DemoService, StateService

router = APIRouter(prefix="/demos", tags=["Demos"])
logger = logging.getLogger(__name__)
demo_service = DemoService()
state_service = StateService()
_vehicle_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_active_demo_cancel_events: dict[int, asyncio.Event] = {}


def cancel_demo(id_vehiculo: int) -> None:
    """Señala la demo activa para que DETENER la cancele inmediatamente."""
    event = _active_demo_cancel_events.get(id_vehiculo)
    if event is not None:
        event.set()


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


async def _publish_demo_stop(
    id_vehiculo: int,
    id_demo: int,
    stop_cmd: dict[str, Any] | None,
) -> None:
    """Publica DETENER (codigo=0) en pausas de demo y al finalizar la secuencia."""
    stop_id = int(stop_cmd["id_comando"]) if stop_cmd and stop_cmd.get("id_comando") else 0
    stop_name = str(stop_cmd.get("nombre") or "DETENER") if stop_cmd else "DETENER"

    stop_event = {
        "event": "nuevo_movimiento",
        "id_demo": id_demo,
        "id_vehiculo": id_vehiculo,
        "id_comando": stop_id,
        "comando": stop_name,
        "codigo": 0,
        "conectado": True,
        "origen": "DEMO",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await manager.broadcast_to_devices(
        id_vehiculo,
        {**stop_event, "destino": "DISPOSITIVO"},
    )
    await manager.broadcast_to_clients(id_vehiculo, stop_event)

    if stop_id > 0:
        await asyncio.to_thread(
            state_service.update,
            id_vehiculo,
            stop_id,
            True,
        )


@router.post(
    "/ejecutar",
    response_model=DemoEjecucionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ejecutar demo en el vehículo sin registrar historial",
)
async def ejecutar_demo(
    body: DemoEjecucionRequest,
    context: AuthContext = Depends(get_auth_context),
) -> DemoEjecucionResponse:
    """Reproduce movimientos ordenados y los publica en el canal del vehículo."""
    try:
        movimientos = await asyncio.to_thread(demo_service.list_movements, body.id_demo)
        if not movimientos:
            raise HTTPException(status_code=404, detail="La demo no tiene movimientos")

        movimientos = sorted(movimientos, key=lambda movimiento: movimiento["orden"])
        access_repository = AccessRepository()
        id_vehiculo = await asyncio.to_thread(access_repository.demo_vehicle, body.id_demo)
        if id_vehiculo is None:
            raise HTTPException(status_code=404, detail="Demo no encontrada")
        demo_scope = await asyncio.to_thread(OwnerDemoRepository().get_demo_scope, body.id_demo)
        if demo_scope is None:
            raise HTTPException(status_code=404, detail="Demo no encontrada")
        if (
            demo_scope["alcance"] == "USUARIO"
            and "INVITADO" in context.roles
        ):
            raise HTTPException(status_code=403, detail="El modo invitado solo puede ejecutar demos de empresa.")
        if (
            demo_scope["alcance"] == "USUARIO"
            and "ADMIN" not in context.roles
            and int(context.user_id or 0) != int(demo_scope["id_usuario"])
        ):
            raise HTTPException(status_code=404, detail="Demo no encontrada")
        total_duration = sum(
            int(movement.get("duracion_ms") or 0) + int(movement.get("pausa_ms") or 0)
            for movement in movimientos
        )
        if len(movimientos) > int(demo_scope["max_pasos"] or 100):
            raise HTTPException(status_code=422, detail="La demo supera el máximo de pasos permitido")
        if total_duration > int(demo_scope["duracion_max_ms"] or 300000):
            raise HTTPException(status_code=422, detail="La demo supera la duración máxima de 300000 ms")
        await asyncio.to_thread(authorize_vehicle, context, id_vehiculo)
        if body.id_vehiculo is not None and body.id_vehiculo != id_vehiculo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El vehículo indicado no coincide con el vehículo asociado a la demo",
            )

        # Evita enviar una secuencia a un vehículo distinto por datos inconsistentes.
        for movimiento in movimientos:
            if await asyncio.to_thread(
                access_repository.allowed_command,
                id_vehiculo,
                movimiento["id_comando"],
            ) is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="La demo contiene un comando no permitido para el modelo de la unidad",
                )
            for key in ("id_vehiculo", "vehiculo_id"):
                row_vehicle_id = movimiento.get(key)
                if row_vehicle_id is not None and row_vehicle_id != id_vehiculo:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="La demo contiene movimientos asociados a vehículos distintos",
                    )

        stop_cmd = await asyncio.to_thread(
            access_repository.command_by_code,
            id_vehiculo,
            0,
        )

        total = len(movimientos)
        async with _vehicle_locks[id_vehiculo]:
            cancel_event = asyncio.Event()
            _active_demo_cancel_events[id_vehiculo] = cancel_event
            if manager.device_connection_count(id_vehiculo) == 0:
                _active_demo_cancel_events.pop(id_vehiculo, None)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"No hay una conexión WebSocket de hardware activa para el vehículo {id_vehiculo}",
                )

            executed = 0
            cancelled = False
            try:
                for index, movimiento in enumerate(movimientos, start=1):
                    if cancel_event.is_set():
                        cancelled = True
                        break
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

                    delivered = await manager.broadcast_to_devices(
                        id_vehiculo,
                        {**event, "destino": "DISPOSITIVO"},
                    )
                    await manager.broadcast_to_clients(id_vehiculo, event)
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

                    try:
                        await asyncio.wait_for(
                            cancel_event.wait(), movimiento["duracion_ms"] / 1000
                        )
                        cancelled = True
                        break
                    except asyncio.TimeoutError:
                        pass

                    if index < total and movimiento["pausa_ms"] > 0:
                        await _publish_demo_stop(id_vehiculo, body.id_demo, stop_cmd)
                        try:
                            await asyncio.wait_for(
                                cancel_event.wait(), movimiento["pausa_ms"] / 1000
                            )
                            cancelled = True
                            break
                        except asyncio.TimeoutError:
                            pass

                # Al terminar todos los pasos sin cancelación, detener el vehículo.
                if not cancelled and executed > 0:
                    await _publish_demo_stop(id_vehiculo, body.id_demo, stop_cmd)
            finally:
                if _active_demo_cancel_events.get(id_vehiculo) is cancel_event:
                    _active_demo_cancel_events.pop(id_vehiculo, None)

        return DemoEjecucionResponse(
            message="Ejecución de DEMO cancelada por DETENER" if cancelled else "Ejecución de DEMO completada correctamente",
            id_demo=body.id_demo,
            id_vehiculo=id_vehiculo,
            total_movimientos=total,
            movimientos_ejecutados=executed,
        )
    except Exception as exc:
        raise _db_error(exc) from exc