"""Pruebas aisladas de autenticación y aislamiento del hardware de Etapa 8."""

import pytest
from fastapi import HTTPException

from app.security import authenticate_device_token


class ImmediateAwaitable:
    def __init__(self, value=None):
        self.value = value

    def __await__(self):
        if False:
            yield
        return self.value


def run_without_event_loop(coroutine):
    iterator = coroutine.__await__()
    try:
        iterator.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("La coroutine de prueba realizó una espera no simulada")


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    def send_json(self, message):
        self.messages.append(message)
        return ImmediateAwaitable()


def test_device_token_is_bound_to_exact_vehicle(monkeypatch):
    monkeypatch.setattr("app.security.DEVICE_TOKENS", {1: "device-secret-1"})

    context = authenticate_device_token("device-secret-1", 1)
    assert context.device_vehicle_id == 1
    assert context.roles == frozenset({"DISPOSITIVO"})

    with pytest.raises(HTTPException) as invalid:
        authenticate_device_token("wrong-secret", 1)
    assert invalid.value.status_code == 401

    with pytest.raises(HTTPException) as wrong_vehicle:
        authenticate_device_token("device-secret-1", 2)
    assert wrong_vehicle.value.status_code == 403


def test_device_and_client_channels_are_isolated(monkeypatch):
    import app.routers.hardware_ws as hardware_ws

    manager = hardware_ws.ConnectionManager()
    client_one = FakeWebSocket()
    client_two = FakeWebSocket()
    device_one = FakeWebSocket()
    device_two = FakeWebSocket()
    manager.active_connections[1] = [client_one]
    manager.active_connections[2] = [client_two]
    manager.device_connections[1] = [device_one]
    manager.device_connections[2] = [device_two]
    monkeypatch.setattr(hardware_ws, "manager", manager)

    stop = {"event": "nuevo_movimiento", "id_vehiculo": 1, "codigo": 0, "destino": "DISPOSITIVO"}
    assert run_without_event_loop(manager.broadcast_to_devices(1, stop)) == 1
    assert device_one.messages == [stop]
    assert device_two.messages == []
    assert client_one.messages == []

    telemetry = '{"event":"telemetria","id_vehiculo":1,"bateria":93}'
    run_without_event_loop(hardware_ws.relay_device_message(device_one, 1, telemetry))
    assert client_one.messages[-1]["origen"] == "DISPOSITIVO"
    assert client_one.messages[-1]["bateria"] == 93
    assert client_two.messages == []


def test_device_cannot_relay_telemetry_for_other_vehicle(monkeypatch):
    import app.routers.hardware_ws as hardware_ws

    with pytest.raises(HTTPException) as error:
        run_without_event_loop(
            hardware_ws.relay_device_message(
                FakeWebSocket(),
                1,
                '{"event":"telemetria","id_vehiculo":2}',
            )
        )
    assert error.value.status_code == 403


def test_device_disconnect_is_audited(monkeypatch):
    import app.routers.hardware_ws as hardware_ws

    audit_rows = []

    class FakeAudit:
        def add_audit(self, **values):
            audit_rows.append(values)

    class FakeAsyncio:
        @staticmethod
        def to_thread(function, *args, **kwargs):
            return ImmediateAwaitable(function(*args, **kwargs))

    monkeypatch.setattr(hardware_ws, "audit_repository", FakeAudit())
    monkeypatch.setattr(hardware_ws, "asyncio", FakeAsyncio())
    run_without_event_loop(hardware_ws.record_device_disconnect(1))
    assert audit_rows == [
        {
            "user_id": None,
            "actor_type": "DISPOSITIVO",
            "action": "DEVICE_DISCONNECTED",
            "resource_type": "VEHICULO",
            "resource_id": "1",
            "detail": {"id_vehiculo": 1},
        }
    ]
