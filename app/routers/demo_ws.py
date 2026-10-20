"""WebSocket de reproducción paso a paso de demos.

Cada movimiento actualiza el estado actual mediante ``sp_actualizar_estado``;
deliberadamente no se llama a ``sp_registrar_historial``. Así la demo deja el
último comando en ``estado_vehiculo`` sin contaminar ``historial_comandos``.
"""

import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services import DemoService, StateService
from fastapi.encoders import jsonable_encoder

router = APIRouter(tags=["WebSocket Demo"])
logger = logging.getLogger(__name__)
demo_service = DemoService()
state_service = StateService()


class ConnectionManager:
    """Mantiene las conexiones WebSocket agrupadas por vehículo."""

    def __init__(self) -> None:
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, id_vehiculo: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(id_vehiculo, []).append(websocket)

    def disconnect(self, id_vehiculo: int, websocket: WebSocket) -> None:
        connections = self.active_connections.get(id_vehiculo)
        if connections is None:
            return

        try:
            connections.remove(websocket)
        except ValueError:
            return

        if not connections:
            self.active_connections.pop(id_vehiculo, None)

    async def broadcast_to_vehicle(self, id_vehiculo: int, message: dict) -> None:
        """Envía el mensaje a los clientes del vehículo y limpia los caídos."""
        for websocket in list(self.active_connections.get(id_vehiculo, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(id_vehiculo, websocket)


manager = ConnectionManager()

# Flag por conexión para cancelar la demo en curso
_stop_flags: dict[int, bool] = {}


@router.websocket("/ws/vehiculo/{id_vehiculo}")
async def websocket_vehiculo(websocket: WebSocket, id_vehiculo: int):
    """Monitorea los cambios de estado de un vehículo en tiempo real."""
    await manager.connect(id_vehiculo, websocket)
    try:
        try:
            rows = await asyncio.to_thread(state_service.get, id_vehiculo)
            await websocket.send_json({
                "event": "estado_actual",
                "id_vehiculo": id_vehiculo,
                "estado": jsonable_encoder(rows[0]),
            })
        except Exception as exc:
            await websocket.send_json({"event": "error", "detail": str(exc)})

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WS vehículo desconectado id_vehiculo=%s", id_vehiculo)
    finally:
        manager.disconnect(id_vehiculo, websocket)


@router.websocket("/ws/demo")
async def websocket_demo(websocket: WebSocket):
    """
    WebSocket que ejecuta una demo paso a paso.

    No registra historial — la prueba 3 verifica explícitamente que
    ``historial_comandos`` permanece sin cambios durante la ejecución.
    """
    await websocket.accept()
    conn_id = id(websocket)
    _stop_flags[conn_id] = False
    logger.info("WS conectado id=%s", conn_id)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "detail": "JSON inválido"})
                continue

            if not isinstance(msg, dict):
                await websocket.send_json({
                    "event": "error",
                    "detail": "El mensaje debe ser un objeto JSON",
                })
                continue

            action = msg.get("action", "")

            # ── STOP ──────────────────────────────────────────────────────────
            if action == "stop":
                _stop_flags[conn_id] = True
                await websocket.send_json({"event": "stopped"})
                continue

            # ── START ─────────────────────────────────────────────────────────
            if action == "start":
                id_demo = msg.get("id_demo")
                if not isinstance(id_demo, int) or id_demo <= 0:
                    await websocket.send_json({"event": "error", "detail": "Falta id_demo"})
                    continue

                # La llamada al driver es bloqueante; no debe detener el
                # event loop que atiende otras conexiones WebSocket.
                try:
                    movimientos = await asyncio.to_thread(demo_service.list_movements, id_demo)
                except Exception as exc:
                    await websocket.send_json({"event": "error", "detail": str(exc)})
                    continue

                if not movimientos:
                    await websocket.send_json(
                        {"event": "error", "detail": f"No hay movimientos para la demo {id_demo}"}
                    )
                    continue

                # El SP puede devolver id_vehiculo mediante el JOIN con demos;
                # también se acepta en el mensaje para instalaciones antiguas.
                id_vehiculo = (
                    msg.get("id_vehiculo")
                    or movimientos[0].get("id_vehiculo")
                    or movimientos[0].get("vehiculo_id")
                )
                if not isinstance(id_vehiculo, int) or id_vehiculo <= 0:
                    await websocket.send_json({
                        "event": "error",
                        "detail": "Falta id_vehiculo para actualizar el estado",
                    })
                    continue

                movimientos = sorted(movimientos, key=lambda item: item["orden"])
                total = len(movimientos)
                _stop_flags[conn_id] = False

                # ── Evento de inicio ───────────────────────────────────────────
                await websocket.send_json(
                    {"event": "demo_start", "id_demo": id_demo, "total": total}
                )

                # ── Reproducir cada movimiento ─────────────────────────────────
                for idx, mov in enumerate(movimientos, start=1):
                    if _stop_flags.get(conn_id):
                        await websocket.send_json({"event": "stopped"})
                        break

                    try:
                        # Prueba 3: actualizar estado sin insertar historial.
                        await asyncio.to_thread(
                            state_service.update,
                            id_vehiculo,
                            mov["id_comando"],
                            True,
                        )
                    except Exception as exc:
                        await websocket.send_json({"event": "error", "detail": str(exc)})
                        break

                    await websocket.send_json({
                        "event": "movimiento",
                        "paso": idx,
                        "total": total,
                        "orden": mov["orden"],
                        "id_comando": mov["id_comando"],
                        "comando": mov["comando"],
                        "codigo": mov["codigo"],
                        "duracion_ms": mov["duracion_ms"],
                        "pausa_ms": mov["pausa_ms"],
                    })

                    # Respetar tiempos definidos en la demo
                    await asyncio.sleep(mov["duracion_ms"] / 1000)

                    if not _stop_flags.get(conn_id) and mov["pausa_ms"] > 0:
                        await asyncio.sleep(mov["pausa_ms"] / 1000)

                else:
                    # For-else: se ejecuta si NO hubo break (ningún stop)
                    await websocket.send_json(
                        {"event": "done", "id_demo": id_demo, "total": total}
                    )

            else:
                await websocket.send_json(
                    {"event": "error", "detail": f"Acción desconocida: '{action}'"}
                )

    except WebSocketDisconnect:
        logger.info("WS desconectado id=%s", conn_id)
    finally:
        _stop_flags.pop(conn_id, None)
