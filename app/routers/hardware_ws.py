"""Canal WebSocket aislado para clientes web y hardware por vehículo."""

import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.repositories.auth import AccessRepository, AuthRepository
from app.security import (
    AuthContext,
    authenticate_device_token,
    authenticate_websocket_token,
    authorize_vehicle,
    is_device_context,
)
from app.services import HistoryService, StateService
from app.services_guest import GuestService


router = APIRouter(tags=["WebSocket Vehículos"])
logger = logging.getLogger(__name__)
state_service = StateService()
history_service = HistoryService()
access_repository = AccessRepository()
guest_service = GuestService()
audit_repository = AuthRepository()


class ConnectionManager:
    """Mantiene separados los sockets de hardware y clientes por vehículo."""

    def __init__(self) -> None:
        # active_connections conserva el nombre y la forma legacy para clientes.
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.device_connections: Dict[int, List[WebSocket]] = {}

    async def connect(
        self,
        id_vehiculo: int,
        websocket: WebSocket,
        subprotocol: str | None = None,
        connection_type: str = "CLIENTE",
    ) -> None:
        if connection_type not in {"CLIENTE", "DISPOSITIVO"}:
            raise ValueError("Tipo de conexión WebSocket inválido")
        await websocket.accept(subprotocol=subprotocol)
        target = self.device_connections if connection_type == "DISPOSITIVO" else self.active_connections
        target.setdefault(id_vehiculo, []).append(websocket)

    def disconnect(self, id_vehiculo: int, websocket: WebSocket) -> None:
        for collection in (self.active_connections, self.device_connections):
            connections = collection.get(id_vehiculo)
            if connections is None:
                continue
            try:
                connections.remove(websocket)
            except ValueError:
                continue
            if not connections:
                collection.pop(id_vehiculo, None)

    def connection_count(self, id_vehiculo: int) -> int:
        return len(self.active_connections.get(id_vehiculo, [])) + len(self.device_connections.get(id_vehiculo, []))

    def device_connection_count(self, id_vehiculo: int) -> int:
        return len(self.device_connections.get(id_vehiculo, []))

    def subscribers_for_vehicle(self, id_vehiculo: int) -> tuple[WebSocket, ...]:
        """Vista inmutable de los suscriptores CLIENTE para aislamiento/test."""
        return tuple(self.active_connections.get(id_vehiculo, []))

    def device_subscribers_for_vehicle(self, id_vehiculo: int) -> tuple[WebSocket, ...]:
        return tuple(self.device_connections.get(id_vehiculo, []))

    async def _broadcast(self, id_vehiculo: int, message: dict, target: Dict[int, List[WebSocket]]) -> int:
        delivered = 0
        for websocket in list(target.get(id_vehiculo, [])):
            try:
                await websocket.send_json(message)
                delivered += 1
            except Exception:
                self.disconnect(id_vehiculo, websocket)
        return delivered

    async def broadcast_to_clients(self, id_vehiculo: int, message: dict) -> int:
        return await self._broadcast(id_vehiculo, message, self.active_connections)

    async def broadcast_to_devices(self, id_vehiculo: int, message: dict) -> int:
        return await self._broadcast(id_vehiculo, message, self.device_connections)

    async def broadcast_to_vehicle(self, id_vehiculo: int, message: dict) -> int:
        """Compatibilidad legacy: difunde únicamente a clientes autorizados."""
        return await self.broadcast_to_clients(id_vehiculo, message)


manager = ConnectionManager()


async def stop_vehicle_safely(id_vehiculo: int) -> None:
    """Registra y publica DETENER para liberar una sesión de exhibición."""
    command = await asyncio.to_thread(access_repository.command_by_code, id_vehiculo, 0)
    if command is None:
        return
    try:
        from app.routers.demo_execution import cancel_demo

        cancel_demo(id_vehiculo)
    except Exception:
        logger.exception("No se pudo señalar la cancelación de demo id_vehiculo=%s", id_vehiculo)
    await asyncio.to_thread(
        history_service.send_command_transactionally,
        id_vehiculo,
        int(command["id_comando"]),
        True,
        "INVITADO",
    )
    message = {
        "event": "nuevo_movimiento",
        "id_vehiculo": id_vehiculo,
        "id_comando": int(command["id_comando"]),
        "codigo": 0,
        "comando": command.get("nombre", "DETENER"),
        "conectado": True,
        "origen": "INVITADO",
    }
    await manager.broadcast_to_devices(id_vehiculo, {**message, "destino": "DISPOSITIVO"})
    await manager.broadcast_to_clients(id_vehiculo, message)


async def release_guest_connection(context: AuthContext | None, expired: bool = False) -> None:
    if context is None or context.guest_session_id is None:
        return
    released = None
    try:
        released = await asyncio.to_thread(
            guest_service.release_connection, context.guest_session_id, expired
        )
    except Exception:
        logger.exception("No se pudo liberar la sesión de invitado id_sesion=%s", context.guest_session_id)

    id_vehiculo = released.get("id_vehiculo") if released else None
    if id_vehiculo is None:
        try:
            session = await asyncio.to_thread(
                guest_service.repository.guest_session_by_id, context.guest_session_id
            )
            if session is not None:
                id_vehiculo = session.get("id_vehiculo")
        except Exception:
            logger.exception(
                "No se pudo resolver el vehículo de la sesión de invitado id_sesion=%s",
                context.guest_session_id,
            )

    should_stop = expired or released is None or released.get("estado") == "ACTIVA"
    if id_vehiculo is not None and should_stop:
        await stop_vehicle_safely(int(id_vehiculo))


async def record_device_disconnect(id_vehiculo: int) -> None:
    try:
        await asyncio.to_thread(
            audit_repository.add_audit,
            user_id=None,
            actor_type="DISPOSITIVO",
            action="DEVICE_DISCONNECTED",
            resource_type="VEHICULO",
            resource_id=str(id_vehiculo),
            detail={"id_vehiculo": id_vehiculo},
        )
    except Exception:
        logger.exception("No se pudo registrar la desconexión del dispositivo id_vehiculo=%s", id_vehiculo)


async def relay_device_message(websocket: WebSocket, id_vehiculo: int, raw_message: str) -> None:
    """Reenvía telemetría/confirmaciones solo a clientes del mismo vehículo."""
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        await websocket.send_json({"event": "error", "detail": "Mensaje de dispositivo no es JSON válido."})
        return
    if not isinstance(payload, dict):
        await websocket.send_json({"event": "error", "detail": "El mensaje del dispositivo debe ser un objeto JSON."})
        return

    reported_vehicle_id = payload.get("id_vehiculo", id_vehiculo)
    try:
        reported_vehicle_id = int(reported_vehicle_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Telemetría sin id_vehiculo válido.") from exc
    if reported_vehicle_id != id_vehiculo:
        raise HTTPException(status_code=403, detail="La telemetría no corresponde al canal del dispositivo.")

    message = dict(payload)
    message["id_vehiculo"] = id_vehiculo
    message["origen"] = "DISPOSITIVO"
    message.setdefault("event", "telemetria_dispositivo")
    await manager.broadcast_to_clients(id_vehiculo, message)


@router.websocket("/ws/vehiculo/{id_vehiculo}")
async def websocket_vehiculo(websocket: WebSocket, id_vehiculo: int):
    """Acepta JWT de cliente o token permanente del hardware antes del handshake."""
    device_token = websocket.query_params.get("device_token") or websocket.headers.get("x-device-token")
    raw_token = websocket.query_params.get("token")
    subprotocols = websocket.scope.get("subprotocols", [])
    selected_subprotocol = None
    if not raw_token and len(subprotocols) >= 2 and subprotocols[0].lower() == "bearer":
        raw_token = subprotocols[1]
        selected_subprotocol = "bearer"
    if device_token and raw_token:
        await websocket.close(code=4403, reason="Use un solo tipo de credencial")
        return
    if not device_token and not raw_token:
        await websocket.close(code=4401, reason="Token requerido")
        return

    context: AuthContext | None = None
    connection_type = "CLIENTE"
    try:
        if device_token:
            context = await asyncio.to_thread(authenticate_device_token, device_token, id_vehiculo)
            connection_type = "DISPOSITIVO"
        else:
            context = await asyncio.to_thread(authenticate_websocket_token, raw_token)
            await asyncio.to_thread(authorize_vehicle, context, id_vehiculo)
    except HTTPException as exc:
        await websocket.close(code=4403 if exc.status_code == 403 else 4401, reason="No autorizado")
        return

    await manager.connect(id_vehiculo, websocket, selected_subprotocol, connection_type)
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
            try:
                incoming = await asyncio.wait_for(websocket.receive_text(), timeout=15)
                if connection_type == "DISPOSITIVO":
                    await relay_device_message(websocket, id_vehiculo, incoming)
            except asyncio.TimeoutError:
                if connection_type == "CLIENTE":
                    # Revocación, expiración o cambio de asignación se detecta aun
                    # cuando el cliente no envíe mensajes por el canal.
                    context = await asyncio.to_thread(authenticate_websocket_token, raw_token)
                    await asyncio.to_thread(authorize_vehicle, context, id_vehiculo)
    except WebSocketDisconnect:
        logger.info("WS vehículo desconectado id_vehiculo=%s tipo=%s", id_vehiculo, connection_type)
        if context is not None and is_device_context(context):
            await record_device_disconnect(id_vehiculo)
        else:
            await release_guest_connection(context)
    except HTTPException:
        if context is not None and is_device_context(context):
            await record_device_disconnect(id_vehiculo)
            await websocket.close(code=4403, reason="Telemetría o canal no autorizado")
        else:
            await release_guest_connection(context, expired=True)
            await websocket.close(code=4403, reason="Permiso revocado o expirado")
    finally:
        manager.disconnect(id_vehiculo, websocket)
