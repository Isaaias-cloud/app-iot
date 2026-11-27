"""Configuracion y ejecucion de movimientos puntuales con duracion."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.repositories.auth import AccessRepository
from app.routers.demo_execution import cancel_demo
from app.routers.hardware_ws import manager
from app.schemas import (
    MovimientoCreate,
    MovimientoEjecucionResponse,
    MovimientoEjecutarRequest,
    MovimientoResponse,
    MovimientoUpdate,
    OperationResponse,
)
from app.security import (
    AuthContext,
    authorize_vehicle,
    get_auth_context,
    require_admin,
    require_allowed_command,
    require_vehicle_access,
)
from app.services import HistoryService, StateService
from app.services_movimientos import MovimientoService

router = APIRouter(prefix="/movimientos", tags=["Movimientos"])
logger = logging.getLogger(__name__)
service = MovimientoService()
history_service = HistoryService()
access_repository = AccessRepository()

_auto_stop_tasks: dict[int, asyncio.Task] = {}


def cancel_movimiento(id_vehiculo: int) -> None:
    """Cancela el auto-paro pendiente de un movimiento puntual."""
    task = _auto_stop_tasks.get(id_vehiculo)
    if task is not None and not task.done():
        task.cancel()
    _auto_stop_tasks.pop(id_vehiculo, None)


async def _publish_auto_stop(id_vehiculo: int, stop_id: int | None) -> None:
    """Publica DETENER sin escribir historial, igual que el paro de demo."""
    event = {
        "event": "auto_stop",
        "id_vehiculo": id_vehiculo,
        "id_comando": stop_id or 0,
        "comando": "DETENER",
        "codigo": 0,
        "conectado": True,
        "origen": "AUTO",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_devices(id_vehiculo, {**event, "destino": "DISPOSITIVO"})
    await manager.broadcast_to_clients(id_vehiculo, event)
    if stop_id and stop_id > 0:
        await asyncio.to_thread(
            StateService().update,
            id_vehiculo,
            stop_id,
            True,
        )


async def _schedule_auto_stop(id_vehiculo: int, duracion_ms: int) -> None:
    """Programa un DETENER automatico tras duracion_ms, cancelable por DETENER."""

    async def _run() -> None:
        try:
            await asyncio.sleep(duracion_ms / 1000)
            stop = await asyncio.to_thread(access_repository.command_by_code, id_vehiculo, 0)
            await _publish_auto_stop(id_vehiculo, int(stop["id_comando"]) if stop else None)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("No se pudo publicar el auto-paro del vehiculo %s", id_vehiculo)
        finally:
            if _auto_stop_tasks.get(id_vehiculo) is task:
                _auto_stop_tasks.pop(id_vehiculo, None)

    cancel_movimiento(id_vehiculo)
    task = asyncio.create_task(_run())
    _auto_stop_tasks[id_vehiculo] = task


def _db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    logger.exception("Error al gestionar movimientos", exc_info=exc)
    return HTTPException(status_code=500, detail=f"Error al gestionar el movimiento: {exc}")


@router.get("/vehiculo/{id_vehiculo}", response_model=list[MovimientoResponse])
def listar_movimientos(
    id_vehiculo: int = Path(..., gt=0),
    _context: AuthContext = Depends(require_vehicle_access),
):
    """Lista los movimientos configurados para una unidad."""
    try:
        return service.list_for_vehicle(int(id_vehiculo))
    except Exception as exc:
        raise _db_error(exc) from exc


@router.post("/", response_model=MovimientoResponse, status_code=status.HTTP_201_CREATED)
def crear_movimiento(body: MovimientoCreate, _context: AuthContext = Depends(require_admin)):
    try:
        return service.create(body.model_dump())
    except Exception as exc:
        raise _db_error(exc) from exc


@router.put("/{id_movimiento}", response_model=MovimientoResponse)
def actualizar_movimiento(
    body: MovimientoUpdate,
    id_movimiento: int,
    _context: AuthContext = Depends(require_admin),
):
    try:
        return service.update(id_movimiento, body.model_dump())
    except Exception as exc:
        raise _db_error(exc) from exc


@router.delete("/{id_movimiento}", response_model=OperationResponse)
def desactivar_movimiento(id_movimiento: int, _context: AuthContext = Depends(require_admin)):
    try:
        return service.deactivate(id_movimiento)
    except Exception as exc:
        raise _db_error(exc) from exc


@router.post("/ejecutar", response_model=MovimientoEjecucionResponse)
async def ejecutar_movimiento(
    body: MovimientoEjecutarRequest,
    context: AuthContext = Depends(get_auth_context),
) -> MovimientoEjecucionResponse:
    """Ejecuta una accion puntual y programa su detencion automatica."""
    try:
        movimiento = service.get(body.id_movimiento)
        id_vehiculo = int(movimiento["id_vehiculo"])
        id_comando = int(movimiento["id_comando"])
        codigo = int(movimiento["codigo"])
        duracion_ms = int(movimiento["duracion_ms"])

        authorize_vehicle(context, id_vehiculo)
        require_allowed_command(id_vehiculo, id_comando)
        cancel_demo(id_vehiculo)
        cancel_movimiento(id_vehiculo)

        await asyncio.to_thread(
            history_service.send_command_transactionally,
            id_vehiculo,
            id_comando,
            True,
            "MOVIMIENTO",
        )

        event = {
            "event": "nuevo_movimiento",
            "id_movimiento": body.id_movimiento,
            "id_vehiculo": id_vehiculo,
            "id_comando": id_comando,
            "codigo": codigo,
            "comando": movimiento.get("comando") or movimiento.get("nombre"),
            "conectado": True,
            "origen": "MOVIMIENTO",
            "duracion_ms": duracion_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await manager.broadcast_to_devices(id_vehiculo, {**event, "destino": "DISPOSITIVO"})
        await manager.broadcast_to_clients(id_vehiculo, event)
        await _schedule_auto_stop(id_vehiculo, duracion_ms)

        return MovimientoEjecucionResponse(
            message="Movimiento ejecutado; detencion automatica programada",
            id_movimiento=body.id_movimiento,
            id_vehiculo=id_vehiculo,
            id_comando=id_comando,
            codigo=codigo,
            duracion_ms=duracion_ms,
        )
    except Exception as exc:
        raise _db_error(exc) from exc
