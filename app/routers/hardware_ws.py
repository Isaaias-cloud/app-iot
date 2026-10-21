"""Canal WebSocket global para notificaciones y control por vehículo."""

import asyncio
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.services import StateService

router = APIRouter(tags=["WebSocket Vehículos"])
logger = logging.getLogger(__name__)
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

    def connection_count(self, id_vehiculo: int) -> int:
        return len(self.active_connections.get(id_vehiculo, []))

    async def broadcast_to_vehicle(self, id_vehiculo: int, message: dict) -> int:
        """Envía el mensaje a los clientes del vehículo y devuelve los envíos exitosos."""
        delivered = 0
        for websocket in list(self.active_connections.get(id_vehiculo, [])):
            try:
                await websocket.send_json(message)
                delivered += 1
            except Exception:
                self.disconnect(id_vehiculo, websocket)
        return delivered


manager = ConnectionManager()


@router.websocket("/ws/vehiculo/{id_vehiculo}")
async def websocket_vehiculo(websocket: WebSocket, id_vehiculo: int):
    """Envía estado inicial y notificaciones de movimiento en tiempo real."""
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
