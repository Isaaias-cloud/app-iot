"""Pruebas aisladas de catálogo, reserva y aislamiento del modo invitado."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.security import AuthContext, authorize_vehicle, require_admin, require_demo_access, require_user_or_admin
from app.services_guest import GuestService


class FakeAudit:
    def __init__(self):
        self.rows = []

    def add_audit(self, **values):
        self.rows.append(values)


class FakeGuestRepository:
    def __init__(self):
        self.result = {
            "id_sesion_invitado": 8,
            "id_vehiculo": 7,
            "inicia_en": datetime.now(timezone.utc).replace(tzinfo=None),
            "expira_en": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=300),
        }
        self.conflict = False
        self.replaced = None
        self.released = {"id_vehiculo": 7, "estado": "ACTIVA"}

    def exhibition_catalog(self):
        return [
            {"id_vehiculo": 7, "estado": "DISPONIBLE"},
            {"id_vehiculo": 8, "estado": "OCUPADA", "libera_en": self.result["expira_en"]},
        ]

    def reserve(self, vehicle_id, token_hash_value):
        if self.conflict:
            return {"conflict": True}
        return {**self.result, "id_vehiculo": vehicle_id}

    def replace_token_hash(self, session_id, token_hash_value):
        self.replaced = (session_id, token_hash_value)

    def release_guest_session(self, session_id, state):
        return self.released


def test_guest_catalog_contains_only_exhibition_states():
    repository = FakeGuestRepository()
    assert [row["estado"] for row in GuestService(repository, FakeAudit()).catalog()] == ["DISPONIBLE", "OCUPADA"]


def test_guest_reservation_uses_300_seconds_and_token(monkeypatch):
    monkeypatch.setattr("app.tokens.JWT_SECRET", "x" * 64)
    repository = FakeGuestRepository()
    audit = FakeAudit()
    result = GuestService(repository, audit).reserve(7, "127.0.0.1")
    assert result["expires_in"] == 300
    assert result["id_vehiculo"] == 7
    assert result["id_sesion_invitado"] == 8
    assert repository.replaced[0] == 8
    assert audit.rows[-1]["actor_type"] == "INVITADO"


def test_second_guest_reservation_returns_409():
    repository = FakeGuestRepository()
    repository.conflict = True
    with pytest.raises(HTTPException) as error:
        GuestService(repository, FakeAudit()).reserve(7, "127.0.0.2")
    assert error.value.status_code == 409


def test_guest_isolation_and_route_roles(monkeypatch):
    monkeypatch.setattr(
        "app.security.access_repository.vehicle_access",
        lambda *args: {"id_vehiculo": 8, "estado_inventario": "EXHIBICION", "es_propietario": False, "tiene_soporte": False, "tiene_reserva": False},
    )
    guest = AuthContext(user_id=None, roles=frozenset({"INVITADO"}), guest_session_id=9)
    with pytest.raises(HTTPException) as error:
        authorize_vehicle(guest, 8)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        require_admin(guest)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        require_user_or_admin(guest)
    assert error.value.status_code == 403


def test_guest_can_access_company_demo_but_not_private(monkeypatch):
    guest = AuthContext(user_id=None, roles=frozenset({"INVITADO"}), guest_session_id=9)
    monkeypatch.setattr("app.security.access_repository.demo_vehicle", lambda demo_id: 7)
    monkeypatch.setattr("app.security.access_repository.vehicle_access", lambda *args: {"id_vehiculo": 7, "estado_inventario": "EXHIBICION", "es_propietario": False, "tiene_soporte": False, "tiene_reserva": True})
    monkeypatch.setattr("app.security.access_repository.demo_scope", lambda demo_id: {"alcance": "EMPRESA", "id_usuario": None})
    assert require_demo_access(1, guest) == guest
    monkeypatch.setattr("app.security.access_repository.demo_scope", lambda demo_id: {"alcance": "USUARIO", "id_usuario": 1})
    with pytest.raises(HTTPException) as error:
        require_demo_access(1, guest)
    assert error.value.status_code == 403


def test_disconnect_releases_guest_reservation():
    repository = FakeGuestRepository()
    service = GuestService(repository, FakeAudit())
    result = service.release_connection(8)
    assert result["id_vehiculo"] == 7
    assert repository.released["estado"] == "ACTIVA"


def test_websocket_release_sends_stop(monkeypatch):
    import app.routers.hardware_ws as hardware_ws

    calls = []

    class ImmediateAwaitable:
        def __init__(self, value=None):
            self.value = value

        def __await__(self):
            if False:
                yield
            return self.value

    class FakeGuestService:
        def release_connection(self, session_id, expired=False):
            return {"id_vehiculo": 7, "estado": "ACTIVA"}

    class FakeAsyncio:
        @staticmethod
        def to_thread(function, *args, **kwargs):
            return ImmediateAwaitable(function(*args, **kwargs))

    def fake_stop(vehicle_id):
        calls.append(vehicle_id)
        return ImmediateAwaitable()

    monkeypatch.setattr(hardware_ws, "guest_service", FakeGuestService())
    monkeypatch.setattr(hardware_ws, "stop_vehicle_safely", fake_stop)
    monkeypatch.setattr(hardware_ws, "asyncio", FakeAsyncio())
    context = AuthContext(user_id=None, roles=frozenset({"INVITADO"}), guest_session_id=8)
    coroutine = hardware_ws.release_guest_connection(context, expired=True)
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    assert completed.value.value is None
    assert calls == [7]


