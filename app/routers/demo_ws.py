"""
WebSocket endpoint — Prueba 3: Ejecutar una DEMO sin registrar historial.

Flujo:
  1. Cliente conecta a  WS /ws/demo
  2. Cliente envía JSON: {"action": "start", "id_demo": <int>}
  3. Servidor carga los movimientos con sp_obtener_movimientos_demo
  4. Emite evento "demo_start" con el total de pasos
  5. Por cada movimiento emite "movimiento" y espera duracion_ms + pausa_ms
  6. Al terminar emite "done"
  7. Cliente puede enviar {"action": "stop"} en cualquier momento

⚠️  IMPORTANTE: esta demo NO llama a sp_registrar_historial ni a
    sp_actualizar_estado, por lo que historial_comandos no se modifica.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.database import call_procedure

router = APIRouter(tags=["WebSocket Demo"])
logger = logging.getLogger(__name__)

# Flag por conexión para cancelar la demo en curso
_stop_flags: dict[int, bool] = {}


@router.websocket("/ws/demo")
async def websocket_demo(websocket: WebSocket):
    """
    WebSocket que ejecuta una demo paso a paso.

    No registra historial — la prueba 3 verifica explícitamente que
    historial_comandos permanece sin cambios durante la ejecución.
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

            action = msg.get("action", "")

            # ── STOP ──────────────────────────────────────────────────────────
            if action == "stop":
                _stop_flags[conn_id] = True
                await websocket.send_json({"event": "stopped"})
                continue

            # ── START ─────────────────────────────────────────────────────────
            if action == "start":
                id_demo = msg.get("id_demo")
                if not id_demo:
                    await websocket.send_json({"event": "error", "detail": "Falta id_demo"})
                    continue

                # Cargar movimientos desde BD (sin historial)
                try:
                    movimientos = call_procedure("sp_obtener_movimientos_demo", (id_demo,))
                except Exception as exc:
                    await websocket.send_json({"event": "error", "detail": str(exc)})
                    continue

                if not movimientos:
                    await websocket.send_json(
                        {"event": "error", "detail": f"No hay movimientos para la demo {id_demo}"}
                    )
                    continue

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

                    await websocket.send_json(
                        {
                            "event":       "movimiento",
                            "paso":        idx,
                            "total":       total,
                            "orden":       mov["orden"],
                            "id_comando":  mov["id_comando"],
                            "comando":     mov["comando"],
                            "codigo":      mov["codigo"],
                            "duracion_ms": mov["duracion_ms"],
                            "pausa_ms":    mov["pausa_ms"],
                        }
                    )

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
